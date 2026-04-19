from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from polymarket_quant.domain.simulation import (
    CashLedgerEntry,
    LiquidityRole,
    OrderSide,
    OrderStateTransition,
    OrderStatus,
    OrderType,
    PositionLedgerEntry,
    RiskCheckResult,
    RiskDecision,
    RiskDecisionType,
    SimulatedFill,
    SimulatedOrder,
    TimeInForce,
    ValuationSnapshot,
)
from polymarket_quant.storage.simulation_store import SimulationStore


SCHEMA_PATH = Path("src/polymarket_quant/storage/postgres_schema.sql")


class FakeResult:
    def __init__(self, row: dict[str, object] | None = None) -> None:
        self.row = row or {"client_order_id": "order-1"}

    def fetchone(self) -> dict[str, object]:
        return self.row

    def fetchall(self) -> list[dict[str, object]]:
        return [self.row]


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, Any] | None]] = []
        self.executed_many: list[tuple[str, list[dict[str, Any]]]] = []
        self.commits = 0

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> FakeResult:
        self.executed.append((sql, params))
        return FakeResult()

    def executemany(self, sql: str, rows: list[dict[str, Any]]) -> None:
        self.executed_many.append((sql, rows))

    def commit(self) -> None:
        self.commits += 1


def instant() -> datetime:
    return datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc)


def order() -> SimulatedOrder:
    return SimulatedOrder(
        client_order_id="order-1",
        strategy_id="strategy-a",
        token_id="token-yes",
        condition_id="0xcondition",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("0.45"),
        size=Decimal("10"),
        remaining_size=Decimal("10"),
        status=OrderStatus.OPEN,
        time_in_force=TimeInForce.GTC,
        created_at=instant(),
        updated_at=instant(),
    )


def fill() -> SimulatedFill:
    return SimulatedFill(
        fill_id="fill-1",
        client_order_id="order-1",
        strategy_id="strategy-a",
        token_id="token-yes",
        condition_id="0xcondition",
        side=OrderSide.BUY,
        price=Decimal("0.45"),
        size=Decimal("2"),
        fee=Decimal("0.01"),
        liquidity_role=LiquidityRole.TAKER,
        created_at=instant(),
    )


def risk_decision() -> RiskDecision:
    return RiskDecision(
        decision=RiskDecisionType.REJECT,
        client_order_id="order-1",
        token_id="token-yes",
        condition_id="0xcondition",
        checks=[
            RiskCheckResult(
                code="INSUFFICIENT_CASH",
                passed=False,
                severity="hard",
                message="Not enough cash",
            )
        ],
        reasons=["INSUFFICIENT_CASH"],
        created_at=instant(),
    )


def valuation() -> ValuationSnapshot:
    return ValuationSnapshot(
        strategy_id="strategy-a",
        token_id="token-yes",
        condition_id="0xcondition",
        quantity=Decimal("2"),
        average_cost=Decimal("0.45"),
        mark_price=Decimal("0.44"),
        mark_reason="BEST_BID",
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("-0.02"),
        core_pnl=Decimal("-0.02"),
        reward_pnl=Decimal("0"),
        total_pnl=Decimal("-0.02"),
        created_at=instant(),
    )


def test_postgres_schema_defines_simulation_layer() -> None:
    schema = SCHEMA_PATH.read_text()

    assert "CREATE SCHEMA IF NOT EXISTS simulation" in schema
    assert "simulation.orders" in schema
    assert "simulation.fills" in schema
    assert "simulation.risk_decisions" in schema
    assert "simulation.valuation_snapshots" in schema
    assert "views.simulation_pnl" in schema
    assert "raw.websocket_events" in schema


def test_store_initializes_full_schema() -> None:
    connection = FakeConnection()
    store = SimulationStore(connection=connection)

    store.init_schema()

    assert "CREATE SCHEMA IF NOT EXISTS simulation" in connection.executed[0][0]
    assert connection.commits == 1


def test_store_upserts_order_and_inserts_transition() -> None:
    connection = FakeConnection()
    store = SimulationStore(connection=connection)

    store.upsert_order(order())
    store.insert_order_transition(
        OrderStateTransition(
            client_order_id="order-1",
            from_status=OrderStatus.PENDING,
            to_status=OrderStatus.OPEN,
            reason="accepted",
            created_at=instant(),
        )
    )

    assert "INSERT INTO simulation.orders" in connection.executed[0][0]
    assert "INSERT INTO simulation.order_transitions" in connection.executed[1][0]


def test_store_inserts_fill_cash_position_and_valuation() -> None:
    connection = FakeConnection()
    store = SimulationStore(connection=connection)

    store.insert_fill(fill())
    store.insert_cash_entry(
        CashLedgerEntry(
            entry_id="cash-1",
            strategy_id="strategy-a",
            client_order_id="order-1",
            fill_id="fill-1",
            delta=Decimal("-0.91"),
            reason="FILL_NOTIONAL",
            created_at=instant(),
        )
    )
    store.insert_position_entry(
        PositionLedgerEntry(
            entry_id="pos-1",
            strategy_id="strategy-a",
            token_id="token-yes",
            condition_id="0xcondition",
            client_order_id="order-1",
            fill_id="fill-1",
            delta=Decimal("2"),
            price=Decimal("0.45"),
            reason="FILL_NOTIONAL",
            created_at=instant(),
        )
    )
    store.insert_valuation_snapshot(valuation())

    assert "INSERT INTO simulation.fills" in connection.executed[0][0]
    assert "INSERT INTO simulation.cash_ledger" in connection.executed[1][0]
    assert "INSERT INTO simulation.position_ledger" in connection.executed[2][0]
    assert "INSERT INTO simulation.valuation_snapshots" in connection.executed[3][0]


def test_store_inserts_risk_decision_as_jsonb_checks() -> None:
    connection = FakeConnection()
    store = SimulationStore(connection=connection)

    store.insert_risk_decision(risk_decision())

    assert "INSERT INTO simulation.risk_decisions" in connection.executed[0][0]
    params = connection.executed[0][1]
    assert params is not None
    assert "checks" in params


def test_store_fetch_helpers_read_simulation_views() -> None:
    connection = FakeConnection()
    store = SimulationStore(connection=connection)

    order_row = store.fetch_order("order-1")
    positions = store.fetch_positions("strategy-a")
    pnl = store.fetch_pnl("strategy-a")

    assert order_row == {"client_order_id": "order-1"}
    assert positions == [{"client_order_id": "order-1"}]
    assert pnl == [{"client_order_id": "order-1"}]
    assert "simulation.orders" in connection.executed[0][0]
    assert "views.simulation_positions" in connection.executed[1][0]
    assert "views.simulation_pnl" in connection.executed[2][0]
