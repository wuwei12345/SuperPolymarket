from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from polymarket_quant.domain.market_data import BookLevel, BookSnapshot
from polymarket_quant.domain.simulation import (
    OrderIntent,
    OrderSide,
    OrderStatus,
)
from polymarket_quant.services.fill_engine import FillEngineConfig
from polymarket_quant.services.order_risk import (
    INSUFFICIENT_CASH,
    MarketConstraints,
    RiskLimits,
)
from polymarket_quant.services.paper_exchange import PaperExchangeService


class RecordingStore:
    def __init__(self) -> None:
        self.events = []
        self.orders = {}
        self.transitions = []
        self.fills = []
        self.cash_entries = []
        self.position_entries = []
        self.risk_decisions = []
        self.valuations = []

    def upsert_order(self, order: object) -> None:
        self.events.append(("order", getattr(order, "status", None)))
        self.orders[getattr(order, "client_order_id")] = order

    def insert_order_transition(self, transition: object) -> None:
        self.events.append(("transition", getattr(transition, "to_status", None)))
        self.transitions.append(transition)

    def insert_fill(self, fill: object) -> None:
        self.events.append(("fill", getattr(fill, "fill_id", None)))
        self.fills.append(fill)

    def insert_cash_entry(self, entry: object) -> None:
        self.events.append(("cash", getattr(entry, "reason", None)))
        self.cash_entries.append(entry)

    def insert_position_entry(self, entry: object) -> None:
        self.events.append(("position", getattr(entry, "reason", None)))
        self.position_entries.append(entry)

    def insert_risk_decision(self, decision: object) -> None:
        self.events.append(("risk", getattr(decision, "decision", None)))
        self.risk_decisions.append(decision)

    def insert_valuation_snapshot(self, snapshot: object) -> None:
        self.events.append(("valuation", getattr(snapshot, "mark_reason", None)))
        self.valuations.append(snapshot)

    def fetch_order(self, client_order_id: str) -> object | None:
        return self.orders.get(client_order_id)


def instant() -> datetime:
    return datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc)


def intent(**overrides: object) -> OrderIntent:
    values = {
        "client_order_id": "order-1",
        "strategy_id": "strategy-a",
        "token_id": "token-yes",
        "condition_id": "0xcondition",
        "side": OrderSide.BUY,
        "price": Decimal("0.48"),
        "size": Decimal("5"),
        "created_at": instant(),
    }
    values.update(overrides)
    return OrderIntent(**values)


def constraints(**overrides: object) -> MarketConstraints:
    values = {
        "token_id": "token-yes",
        "condition_id": "0xcondition",
        "tick_size": Decimal("0.01"),
        "min_order_size": Decimal("1"),
        "best_bid": Decimal("0.44"),
        "best_ask": Decimal("0.46"),
        "spread": Decimal("0.02"),
    }
    values.update(overrides)
    return MarketConstraints(**values)


def limits(**overrides: object) -> RiskLimits:
    values = {
        "cash_available": Decimal("100"),
        "token_position": Decimal("100"),
        "max_single_order_notional": Decimal("100"),
        "max_market_position": Decimal("100"),
        "max_token_position": Decimal("100"),
    }
    values.update(overrides)
    return RiskLimits(**values)


def book() -> BookSnapshot:
    return BookSnapshot(
        token_id="token-yes",
        condition_id="0xcondition",
        source_ts=instant(),
        received_at=instant(),
        bids=[BookLevel(side="BUY", price=Decimal("0.44"), size=Decimal("10"))],
        asks=[BookLevel(side="SELL", price=Decimal("0.46"), size=Decimal("10"))],
        last_trade_price=Decimal("0.45"),
    )


def exchange(store: RecordingStore) -> PaperExchangeService:
    return PaperExchangeService(
        store=store,
        fill_config=FillEngineConfig(submit_latency_ms=0, cancel_latency_ms=0),
    )


def test_submit_records_risk_decision_before_accepting_order() -> None:
    store = RecordingStore()
    result = exchange(store).submit_order_intent(
        intent(), constraints(), limits(), snapshot=book(), now=instant()
    )

    first_order_event = next(
        index for index, event in enumerate(store.events) if event[0] == "order"
    )
    first_risk_event = next(
        index for index, event in enumerate(store.events) if event[0] == "risk"
    )
    assert first_risk_event < first_order_event
    assert result.order is not None
    assert result.order.status == OrderStatus.FILLED
    assert result.fills
    assert result.ledger_updates
    assert result.valuation_snapshot is not None


def test_rejected_order_has_no_fills_or_ledger_updates() -> None:
    store = RecordingStore()
    result = exchange(store).submit_order_intent(
        intent(price=Decimal("0.90"), size=Decimal("20")),
        constraints(),
        limits(cash_available=Decimal("1")),
        snapshot=book(),
        now=instant(),
    )

    assert result.order is not None
    assert result.order.status == OrderStatus.REJECTED
    assert INSUFFICIENT_CASH in result.risk_decision.reasons
    assert result.fills == []
    assert result.ledger_updates == []
    assert store.fills == []
    assert store.cash_entries == []
    assert store.position_entries == []


def test_marketable_limit_order_produces_partial_fill_and_ledger_updates() -> None:
    store = RecordingStore()
    partial_book = BookSnapshot(
        token_id="token-yes",
        condition_id="0xcondition",
        source_ts=instant(),
        received_at=instant(),
        asks=[BookLevel(side="SELL", price=Decimal("0.46"), size=Decimal("2"))],
    )

    result = exchange(store).submit_order_intent(
        intent(size=Decimal("5")), constraints(), limits(), partial_book, instant()
    )

    assert result.order is not None
    assert result.order.status == OrderStatus.PARTIALLY_FILLED
    assert result.order.remaining_size == Decimal("3")
    assert len(result.fills) == 1
    assert len(result.ledger_updates) == 1


def test_cancel_order_uses_lifecycle_transitions() -> None:
    store = RecordingStore()
    service = exchange(store)
    submitted = service.submit_order_intent(
        intent(price=Decimal("0.45")),
        constraints(),
        limits(),
        snapshot=None,
        now=instant(),
    )

    result = service.cancel_order(submitted.order.client_order_id, now=instant())

    assert result.order is not None
    assert result.order.status == OrderStatus.CANCELED
    assert [transition.to_status for transition in result.transitions] == [
        OrderStatus.CANCEL_REQUESTED,
        OrderStatus.CANCELED,
    ]


def test_replace_order_runs_risk_checks_for_replacement() -> None:
    store = RecordingStore()
    service = exchange(store)
    service.submit_order_intent(
        intent(price=Decimal("0.45")),
        constraints(),
        limits(),
        snapshot=None,
        now=instant(),
    )

    result = service.replace_order(
        "order-1",
        intent(client_order_id="order-2", price=Decimal("0.455")),
        constraints(),
        limits(),
        snapshot=None,
        now=instant(),
    )

    assert result.order is not None
    assert result.order.client_order_id == "order-2"
    assert result.order.status == OrderStatus.REJECTED
    assert result.risk_decision.reasons == ["INVALID_TICK_SIZE"]
    assert any(
        transition.to_status == OrderStatus.REPLACE_REQUESTED
        for transition in result.transitions
    )


def test_readme_documents_phase3_paper_exchange_scope() -> None:
    readme = Path("README.md").read_text()

    assert "## Phase 3 Paper Exchange" in readme
    assert "OrderIntent" in readme
    assert "marketable limit" in readme
    assert "RiskDecision" in readme
    assert "Deferred beyond P0" in readme
    assert "Phase 3 does not place live orders or use wallet authentication." in readme
