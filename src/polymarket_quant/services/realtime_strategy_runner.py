from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field

from polymarket_quant.domain.simulation import OrderIntent, OrderStatus
from polymarket_quant.domain.strategy import StrategyEvent, StrategyEventType, StrategySignal
from polymarket_quant.services.order_risk import MarketConstraints, RiskLimits
from polymarket_quant.services.paper_exchange import PaperExchangeService, PaperOrderResult
from polymarket_quant.services.signal_execution import SignalExecutionService
from polymarket_quant.services.strategy_runtime import StrategyRuntime


ConstraintsProvider = Callable[[StrategySignal], MarketConstraints]
LimitsProvider = Callable[[StrategySignal], RiskLimits]
SnapshotProvider = Callable[[StrategySignal], object | None]


class RealtimeExecutionResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    signals: list[StrategySignal] = Field(default_factory=list)
    order_intents: list[OrderIntent] = Field(default_factory=list)
    paper_results: list[PaperOrderResult] = Field(default_factory=list)


class RealtimeStrategyRunner:
    def __init__(
        self,
        runtime: StrategyRuntime,
        signal_execution: SignalExecutionService,
        paper_exchange: PaperExchangeService,
        constraints_provider: ConstraintsProvider,
        limits_provider: LimitsProvider,
        snapshot_provider: SnapshotProvider | None = None,
    ) -> None:
        self.runtime = runtime
        self.signal_execution = signal_execution
        self.paper_exchange = paper_exchange
        self.constraints_provider = constraints_provider
        self.limits_provider = limits_provider
        self.snapshot_provider = snapshot_provider or (lambda _signal: None)
        self._positions = self._restore_positions()
        self._cash = self._restore_cash()
        self._orders: dict[str, dict[str, object]] = {}

    def on_init(self, timestamp: datetime) -> RealtimeExecutionResult:
        signals = self.runtime.on_init(timestamp)
        return self._dispatch_signals(signals)

    def on_event(self, event: StrategyEvent) -> RealtimeExecutionResult:
        signals = self.runtime.on_event(event)
        return self._dispatch_signals(signals)

    def on_clock(self, timestamp: datetime) -> RealtimeExecutionResult:
        signals = self.runtime.on_clock(timestamp)
        return self._dispatch_signals(signals)

    def on_finish(self, timestamp: datetime) -> list[StrategySignal]:
        return self.runtime.on_finish(timestamp)

    def _dispatch_signals(
        self, signals: list[StrategySignal]
    ) -> RealtimeExecutionResult:
        order_intents: list[OrderIntent] = []
        paper_results: list[PaperOrderResult] = []
        for signal in signals:
            context = self.runtime.build_context(signal.ts)
            intents = self.signal_execution.translate_signal(signal, context)
            order_intents.extend(intents)
            for intent in intents:
                result = self.paper_exchange.submit_order_intent(
                    intent,
                    self.constraints_provider(signal),
                    self.limits_provider(signal),
                    snapshot=self.snapshot_provider(signal),
                    now=signal.ts,
                )
                paper_results.append(result)
                self._record_feedback(signal, result)
        return RealtimeExecutionResult(
            signals=signals,
            order_intents=order_intents,
            paper_results=paper_results,
        )

    def _record_feedback(
        self, signal: StrategySignal, result: PaperOrderResult
    ) -> None:
        if result.risk_decision is not None:
            self.runtime.on_event(
                StrategyEvent(
                    event_type=StrategyEventType.RISK,
                    ts=signal.ts,
                    token_id=signal.token_id,
                    condition_id=result.risk_decision.condition_id,
                    source="paper_exchange",
                    payload={
                        "risk_decision": result.risk_decision.model_dump(mode="python")
                    },
                )
            )

        if result.order is None:
            return

        self._update_order_book(result)
        if result.fills:
            for fill in result.fills:
                self._apply_fill(fill.model_dump(mode="python"))
                self.runtime.on_event(
                    StrategyEvent(
                        event_type=StrategyEventType.EXECUTION,
                        ts=signal.ts,
                        token_id=fill.token_id,
                        condition_id=fill.condition_id,
                        source="paper_exchange",
                        payload={
                            "fill": fill.model_dump(mode="python"),
                            "positions": self._serialize_positions(),
                            "cash": self._cash,
                            "open_orders": self._open_orders(),
                        },
                    )
                )
            return

        self.runtime.on_event(
            StrategyEvent(
                event_type=StrategyEventType.EXECUTION,
                ts=signal.ts,
                token_id=result.order.token_id,
                condition_id=result.order.condition_id,
                source="paper_exchange",
                payload={
                    "positions": self._serialize_positions(),
                    "cash": self._cash,
                    "open_orders": self._open_orders(),
                    "order": result.order.model_dump(mode="python"),
                },
            )
        )

    def _update_order_book(self, result: PaperOrderResult) -> None:
        if result.order is None:
            return
        order = result.order.model_dump(mode="python")
        status = order.get("status")
        client_order_id = str(order["client_order_id"])
        if status in {
            OrderStatus.CANCELED,
            OrderStatus.FILLED,
            OrderStatus.REJECTED,
            OrderStatus.REPLACED,
        }:
            self._orders.pop(client_order_id, None)
            return
        self._orders[client_order_id] = order

    def _apply_fill(self, fill: dict[str, object]) -> None:
        token_id = str(fill["token_id"])
        signed_size = self._as_decimal(fill["size"])
        if str(fill["side"]) == "SELL":
            signed_size *= Decimal("-1")
        self._positions[token_id] = self._positions.get(token_id, Decimal("0")) + signed_size

        notional = self._as_decimal(fill["price"]) * self._as_decimal(fill["size"])
        fee = self._as_decimal(fill.get("fee"))
        if str(fill["side"]) == "BUY":
            self._cash -= notional + fee
        else:
            self._cash += notional - fee

    def _serialize_positions(self) -> dict[str, dict[str, Decimal]]:
        return {
            token_id: {"quantity": quantity}
            for token_id, quantity in self._positions.items()
        }

    def _open_orders(self) -> list[dict[str, object]]:
        return list(self._orders.values())

    def _restore_positions(self) -> dict[str, Decimal]:
        positions = self.runtime.state.portfolio.get("positions", {})
        if not isinstance(positions, dict):
            return {}
        restored: dict[str, Decimal] = {}
        for token_id, position in positions.items():
            if isinstance(position, dict) and "quantity" in position:
                restored[token_id] = self._as_decimal(position["quantity"])
            else:
                restored[token_id] = self._as_decimal(position)
        return restored

    def _restore_cash(self) -> Decimal:
        cash = self.runtime.state.portfolio.get("cash")
        return self._as_decimal(cash)

    @staticmethod
    def _as_decimal(value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if value is None:
            return Decimal("0")
        return Decimal(str(value))
