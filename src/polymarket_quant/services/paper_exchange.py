from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polymarket_quant.domain.market_data import BestBidAsk, BookSnapshot, LastTrade, utc_now
from polymarket_quant.domain.simulation import (
    OrderIntent,
    OrderStateTransition,
    OrderStatus,
    PositionState,
    RiskDecision,
    RiskDecisionType,
    SimulatedFill,
    SimulatedOrder,
    ValuationSnapshot,
)
from polymarket_quant.services.fill_engine import (
    FillEngineConfig,
    simulate_fills,
)
from polymarket_quant.services.order_lifecycle import OrderLifecycleService
from polymarket_quant.services.order_risk import (
    MarketConstraints,
    RiskLimits,
    apply_risk_checks,
)
from polymarket_quant.services.portfolio_ledger import (
    LedgerUpdateResult,
    PortfolioLedgerService,
    apply_position_change,
    value_position,
)


RiskEngine = Callable[[OrderIntent, MarketConstraints, RiskLimits], RiskDecision]
FillEngine = Callable[
    [SimulatedOrder, BookSnapshot, FillEngineConfig, datetime | None],
    Any,
]


class PaperOrderResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    order: SimulatedOrder | None
    risk_decision: RiskDecision | None = None
    fills: list[SimulatedFill] = Field(default_factory=list)
    ledger_updates: list[LedgerUpdateResult] = Field(default_factory=list)
    valuation_snapshot: ValuationSnapshot | None = None
    transitions: list[OrderStateTransition] = Field(default_factory=list)


class PaperExchangeService:
    def __init__(
        self,
        store: Any | None = None,
        risk_engine: RiskEngine | None = None,
        lifecycle: OrderLifecycleService | None = None,
        fill_engine: FillEngine | None = None,
        ledger: PortfolioLedgerService | None = None,
        market_data_reader: Any | None = None,
        fill_config: FillEngineConfig | None = None,
    ) -> None:
        self.store = store
        self.risk_engine = risk_engine or apply_risk_checks
        self.lifecycle = lifecycle or OrderLifecycleService()
        self.fill_engine = fill_engine or simulate_fills
        self.ledger = ledger or PortfolioLedgerService(store=store)
        self.market_data_reader = market_data_reader
        self.fill_config = fill_config or FillEngineConfig()
        self._orders: dict[str, SimulatedOrder] = {}

    def submit_order_intent(
        self,
        intent: OrderIntent,
        constraints: MarketConstraints,
        limits: RiskLimits,
        snapshot: BookSnapshot | None = None,
        now: datetime | None = None,
    ) -> PaperOrderResult:
        timestamp = now or utc_now()
        risk_decision = self.risk_engine(intent, constraints, limits)
        self._insert_risk_decision(risk_decision)

        order = self.lifecycle.create_order(intent, now=timestamp)
        transitions: list[OrderStateTransition] = []

        if risk_decision.decision == RiskDecisionType.REJECT:
            order, transition = self.lifecycle.reject(
                order, ",".join(risk_decision.reasons), now=timestamp
            )
            transitions.append(transition)
            self._persist_order(order)
            self._insert_transition(transition)
            return PaperOrderResult(
                order=order,
                risk_decision=risk_decision,
                transitions=transitions,
            )

        order, accepted_transition = self.lifecycle.transition(
            order, OrderStatus.ACCEPTED, "risk_accepted", now=timestamp
        )
        transitions.append(accepted_transition)
        self._persist_order(order)
        self._insert_transition(accepted_transition)

        order, open_transition = self.lifecycle.mark_open(order, now=timestamp)
        transitions.append(open_transition)
        self._persist_order(order)
        self._insert_transition(open_transition)

        fills: list[SimulatedFill] = []
        ledger_updates: list[LedgerUpdateResult] = []
        valuation_snapshot: ValuationSnapshot | None = None
        if snapshot is not None:
            fill_result = self.fill_engine(order, snapshot, self.fill_config, timestamp)
            fills = list(fill_result.fills)
            if fill_result.status == OrderStatus.FILLED:
                order, fill_transition = self.lifecycle.mark_filled(order, now=timestamp)
                transitions.append(fill_transition)
                self._insert_transition(fill_transition)
            elif fill_result.status == OrderStatus.PARTIALLY_FILLED:
                order, fill_transition = self.lifecycle.mark_partially_filled(
                    order, fill_result.remaining_size, now=timestamp
                )
                transitions.append(fill_transition)
                self._insert_transition(fill_transition)
            self._persist_order(order)

            position = PositionState(
                strategy_id=order.strategy_id,
                token_id=order.token_id,
                condition_id=order.condition_id,
            )
            for fill in fills:
                ledger_update = self.ledger.apply_fill(fill, order)
                ledger_updates.append(ledger_update)
                fill = self._fill_with_recorded_fee(fill, ledger_update)
                self._insert_fill(fill)
                position = apply_position_change(position, fill, order)

            if fills:
                valuation_snapshot = value_position(
                    position,
                    self._bbo_from_constraints(constraints),
                    self._last_trade_from_snapshot(snapshot),
                )
                self._insert_valuation_snapshot(valuation_snapshot)

        self._orders[order.client_order_id] = order
        return PaperOrderResult(
            order=order,
            risk_decision=risk_decision,
            fills=fills,
            ledger_updates=ledger_updates,
            valuation_snapshot=valuation_snapshot,
            transitions=transitions,
        )

    def cancel_order(
        self, client_order_id: str, now: datetime | None = None
    ) -> PaperOrderResult:
        timestamp = now or utc_now()
        order = self._load_order(client_order_id)
        order, request_transition = self.lifecycle.request_cancel(order, now=timestamp)
        self._persist_order(order)
        self._insert_transition(request_transition)
        order, cancel_transition = self.lifecycle.cancel(order, now=timestamp)
        self._persist_order(order)
        self._insert_transition(cancel_transition)
        return PaperOrderResult(
            order=order,
            transitions=[request_transition, cancel_transition],
        )

    def replace_order(
        self,
        client_order_id: str,
        replacement: OrderIntent,
        constraints: MarketConstraints,
        limits: RiskLimits,
        snapshot: BookSnapshot | None = None,
        now: datetime | None = None,
    ) -> PaperOrderResult:
        timestamp = now or utc_now()
        original = self._load_order(client_order_id)
        original, request_transition = self.lifecycle.request_replace(
            original, now=timestamp
        )
        self._persist_order(original)
        self._insert_transition(request_transition)

        result = self.submit_order_intent(
            replacement,
            constraints,
            limits,
            snapshot=snapshot,
            now=timestamp,
        )
        if (
            result.risk_decision is not None
            and result.risk_decision.decision == RiskDecisionType.REJECT
        ):
            return result.model_copy(
                update={
                    "transitions": [
                        request_transition,
                        *result.transitions,
                    ]
                }
            )
        original, replaced_transition = self.lifecycle.transition(
            original, OrderStatus.REPLACED, "replaced", now=timestamp
        )
        self._persist_order(original)
        self._insert_transition(replaced_transition)
        return result.model_copy(
            update={
                "transitions": [
                    request_transition,
                    *result.transitions,
                    replaced_transition,
                ]
            }
        )

    def _load_order(self, client_order_id: str) -> SimulatedOrder:
        if client_order_id in self._orders:
            return self._orders[client_order_id]
        if self.store is None or not hasattr(self.store, "fetch_order"):
            raise KeyError(f"unknown order: {client_order_id}")
        record = self.store.fetch_order(client_order_id)
        if record is None:
            raise KeyError(f"unknown order: {client_order_id}")
        if isinstance(record, SimulatedOrder):
            return record
        return SimulatedOrder(**record)

    def _persist_order(self, order: SimulatedOrder) -> None:
        self._orders[order.client_order_id] = order
        if self.store is not None:
            self.store.upsert_order(order)

    def _insert_transition(self, transition: OrderStateTransition) -> None:
        if self.store is not None:
            self.store.insert_order_transition(transition)

    def _insert_risk_decision(self, decision: RiskDecision) -> None:
        if self.store is not None:
            self.store.insert_risk_decision(decision)

    def _insert_fill(self, fill: SimulatedFill) -> None:
        if self.store is not None:
            self.store.insert_fill(fill)

    def _insert_valuation_snapshot(self, snapshot: ValuationSnapshot) -> None:
        if self.store is not None:
            self.store.insert_valuation_snapshot(snapshot)

    @staticmethod
    def _fill_with_recorded_fee(
        fill: SimulatedFill, ledger_update: LedgerUpdateResult
    ) -> SimulatedFill:
        if fill.fee != 0 or ledger_update.fee_entry is None:
            return fill
        return fill.model_copy(update={"fee": -ledger_update.fee_entry.delta})

    @staticmethod
    def _bbo_from_constraints(constraints: MarketConstraints) -> BestBidAsk:
        midpoint = None
        if constraints.best_bid is not None and constraints.best_ask is not None:
            midpoint = (constraints.best_bid + constraints.best_ask) / Decimal("2")
        return BestBidAsk(
            token_id=constraints.token_id,
            condition_id=constraints.condition_id,
            best_bid=constraints.best_bid,
            best_ask=constraints.best_ask,
            spread=constraints.spread,
            midpoint=midpoint,
        )

    @staticmethod
    def _last_trade_from_snapshot(snapshot: BookSnapshot) -> LastTrade | None:
        if snapshot.last_trade_price is None:
            return None
        return LastTrade(
            token_id=snapshot.token_id,
            condition_id=snapshot.condition_id,
            price=snapshot.last_trade_price,
            source_ts=snapshot.source_ts,
            received_at=snapshot.received_at,
            source=snapshot.source,
            collection_run_id=snapshot.collection_run_id,
            gap_fill=snapshot.gap_fill,
        )
