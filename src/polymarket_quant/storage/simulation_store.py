from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence

from polymarket_quant.domain.simulation import (
    CashLedgerEntry,
    OrderStateTransition,
    PositionLedgerEntry,
    RiskDecision,
    SimulatedFill,
    SimulatedOrder,
    ValuationSnapshot,
)
from polymarket_quant.storage.market_data_store import DATABASE_URL_ENV


class SimulationStore:
    def __init__(self, dsn: str | None = None, connection: Any | None = None) -> None:
        self.dsn = dsn or os.getenv(DATABASE_URL_ENV)
        self.connection = connection

    def init_schema(self) -> None:
        schema_sql = Path(__file__).with_name("postgres_schema.sql").read_text()
        with self._connect() as connection:
            connection.execute(schema_sql)
            self._commit(connection)

    def upsert_order(self, order: SimulatedOrder) -> int:
        self._execute(
            """
            INSERT INTO simulation.orders (
                client_order_id, strategy_id, token_id, condition_id, side,
                order_type, price, size, remaining_size, status, time_in_force,
                post_only, expires_at, created_at, accepted_at, updated_at,
                reject_reason
            ) VALUES (
                %(client_order_id)s, %(strategy_id)s, %(token_id)s,
                %(condition_id)s, %(side)s, %(order_type)s, %(price)s, %(size)s,
                %(remaining_size)s, %(status)s, %(time_in_force)s, %(post_only)s,
                %(expires_at)s, %(created_at)s, %(accepted_at)s, %(updated_at)s,
                %(reject_reason)s
            )
            ON CONFLICT (client_order_id) DO UPDATE SET
                remaining_size = EXCLUDED.remaining_size,
                status = EXCLUDED.status,
                accepted_at = EXCLUDED.accepted_at,
                updated_at = EXCLUDED.updated_at,
                reject_reason = EXCLUDED.reject_reason
            """,
            order.model_dump(mode="json"),
        )
        return 1

    def insert_order_transition(self, transition: OrderStateTransition) -> int:
        self._execute(
            """
            INSERT INTO simulation.order_transitions (
                client_order_id, from_status, to_status, reason, created_at
            ) VALUES (
                %(client_order_id)s, %(from_status)s, %(to_status)s,
                %(reason)s, %(created_at)s
            )
            """,
            transition.model_dump(mode="json"),
        )
        return 1

    def insert_fill(self, fill: SimulatedFill) -> int:
        self._execute(
            """
            INSERT INTO simulation.fills (
                fill_id, client_order_id, strategy_id, token_id, condition_id,
                side, price, size, fee, liquidity_role, source_snapshot_id,
                source_ts, created_at
            ) VALUES (
                %(fill_id)s, %(client_order_id)s, %(strategy_id)s, %(token_id)s,
                %(condition_id)s, %(side)s, %(price)s, %(size)s, %(fee)s,
                %(liquidity_role)s, %(source_snapshot_id)s, %(source_ts)s,
                %(created_at)s
            )
            """,
            fill.model_dump(mode="json"),
        )
        return 1

    def insert_cash_entry(self, entry: CashLedgerEntry) -> int:
        self._execute(
            """
            INSERT INTO simulation.cash_ledger (
                entry_id, strategy_id, client_order_id, fill_id, delta, reason,
                created_at
            ) VALUES (
                %(entry_id)s, %(strategy_id)s, %(client_order_id)s, %(fill_id)s,
                %(delta)s, %(reason)s, %(created_at)s
            )
            """,
            entry.model_dump(mode="json"),
        )
        return 1

    def insert_position_entry(self, entry: PositionLedgerEntry) -> int:
        self._execute(
            """
            INSERT INTO simulation.position_ledger (
                entry_id, strategy_id, token_id, condition_id, client_order_id,
                fill_id, delta, price, reason, created_at
            ) VALUES (
                %(entry_id)s, %(strategy_id)s, %(token_id)s, %(condition_id)s,
                %(client_order_id)s, %(fill_id)s, %(delta)s, %(price)s,
                %(reason)s, %(created_at)s
            )
            """,
            entry.model_dump(mode="json"),
        )
        return 1

    def insert_risk_decision(self, decision: RiskDecision) -> int:
        self._execute(
            """
            INSERT INTO simulation.risk_decisions (
                decision, client_order_id, token_id, condition_id, checks,
                reasons, warnings, created_at
            ) VALUES (
                %(decision)s, %(client_order_id)s, %(token_id)s,
                %(condition_id)s, %(checks)s, %(reasons)s, %(warnings)s,
                %(created_at)s
            )
            """,
            decision.model_dump(mode="json"),
        )
        return 1

    def insert_valuation_snapshot(self, snapshot: ValuationSnapshot) -> int:
        self._execute(
            """
            INSERT INTO simulation.valuation_snapshots (
                strategy_id, token_id, condition_id, quantity, average_cost,
                mark_price, mark_reason, realized_pnl, unrealized_pnl, core_pnl,
                reward_pnl, total_pnl, created_at
            ) VALUES (
                %(strategy_id)s, %(token_id)s, %(condition_id)s, %(quantity)s,
                %(average_cost)s, %(mark_price)s, %(mark_reason)s,
                %(realized_pnl)s, %(unrealized_pnl)s, %(core_pnl)s,
                %(reward_pnl)s, %(total_pnl)s, %(created_at)s
            )
            """,
            snapshot.model_dump(mode="json"),
        )
        return 1

    def fetch_order(self, client_order_id: str) -> dict[str, Any] | None:
        rows = self._fetch_all(
            """
            SELECT * FROM simulation.orders
            WHERE client_order_id = %(client_order_id)s
            """,
            {"client_order_id": client_order_id},
        )
        return rows[0] if rows else None

    def fetch_positions(self, strategy_id: str | None = None) -> list[dict[str, Any]]:
        if strategy_id is None:
            return self._fetch_all("SELECT * FROM views.simulation_positions", {})
        return self._fetch_all(
            """
            SELECT * FROM views.simulation_positions
            WHERE strategy_id = %(strategy_id)s
            """,
            {"strategy_id": strategy_id},
        )

    def fetch_pnl(self, strategy_id: str | None = None) -> list[dict[str, Any]]:
        if strategy_id is None:
            return self._fetch_all("SELECT * FROM views.simulation_pnl", {})
        return self._fetch_all(
            """
            SELECT * FROM views.simulation_pnl
            WHERE strategy_id = %(strategy_id)s
            """,
            {"strategy_id": strategy_id},
        )

    def _connect(self) -> Any:
        if self.connection is not None:
            return _ConnectionContext(self.connection)
        if not self.dsn:
            raise ValueError("DATABASE_URL is required for SimulationStore")
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(self.dsn, row_factory=dict_row)

    def _execute(self, sql: str, params: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(sql, self._adapt_params(params))
            self._commit(connection)

    def _executemany(self, sql: str, rows: Sequence[dict[str, Any]]) -> None:
        with self._connect() as connection:
            connection.executemany(sql, [self._adapt_params(row) for row in rows])
            self._commit(connection)

    def _fetch_all(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        with self._connect() as connection:
            result = connection.execute(sql, params)
            rows = result.fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _commit(connection: Any) -> None:
        commit = getattr(connection, "commit", None)
        if callable(commit):
            commit()

    @staticmethod
    def _adapt_params(params: dict[str, Any]) -> dict[str, Any]:
        adapted = dict(params)
        checks = adapted.get("checks")
        if checks is not None:
            try:
                from psycopg.types.json import Jsonb
            except ImportError:
                pass
            else:
                adapted["checks"] = Jsonb(checks)
        return adapted


class _ConnectionContext:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def __enter__(self) -> Any:
        return self.connection

    def __exit__(self, *_exc: object) -> None:
        return None
