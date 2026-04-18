from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence

from polymarket_quant.domain.market_data import (
    BestBidAsk,
    BookSnapshot,
    GapFillInterval,
    LastTrade,
    PriceHistoryPoint,
    RawPayloadEnvelope,
    ReferenceToken,
)

DATABASE_URL_ENV = "DATABASE_URL"


class MarketDataStore:
    def __init__(self, dsn: str | None = None, connection: Any | None = None) -> None:
        self.dsn = dsn or os.getenv(DATABASE_URL_ENV)
        self.connection = connection

    def init_schema(self) -> None:
        schema_sql = Path(__file__).with_name("postgres_schema.sql").read_text()
        with self._connect() as connection:
            connection.execute(schema_sql)
            self._commit(connection)

    def upsert_reference_tokens(self, tokens: Sequence[ReferenceToken]) -> int:
        rows = [token.model_dump(mode="json") for token in tokens]
        if not rows:
            return 0
        sql = """
            INSERT INTO reference.tokens (
                token_id, condition_id, market_id, question, outcome, category,
                liquidity, end_date, active, accepting_orders, universe_rank,
                selection_reason, created_at, updated_at
            ) VALUES (
                %(token_id)s, %(condition_id)s, %(market_id)s, %(question)s,
                %(outcome)s, %(category)s, %(liquidity)s, %(end_date)s,
                %(active)s, %(accepting_orders)s, %(universe_rank)s,
                %(selection_reason)s, %(created_at)s, now()
            )
            ON CONFLICT (token_id) DO UPDATE SET
                condition_id = EXCLUDED.condition_id,
                market_id = EXCLUDED.market_id,
                question = EXCLUDED.question,
                outcome = EXCLUDED.outcome,
                category = EXCLUDED.category,
                liquidity = EXCLUDED.liquidity,
                end_date = EXCLUDED.end_date,
                active = EXCLUDED.active,
                accepting_orders = EXCLUDED.accepting_orders,
                universe_rank = EXCLUDED.universe_rank,
                selection_reason = EXCLUDED.selection_reason,
                updated_at = now()
        """
        self._executemany(sql, rows)
        return len(rows)

    def insert_raw_rest_payload(self, envelope: RawPayloadEnvelope) -> int:
        row = self._envelope_row(envelope)
        sql = """
            INSERT INTO raw.rest_payloads (
                source, endpoint, token_id, condition_id, payload, source_ts,
                received_at, collection_run_id, connection_id, gap_fill
            ) VALUES (
                %(source)s, %(endpoint)s, %(token_id)s, %(condition_id)s,
                %(payload)s, %(source_ts)s, %(received_at)s, %(collection_run_id)s,
                %(connection_id)s, %(gap_fill)s
            )
        """
        self._execute(sql, row)
        return 1

    def insert_raw_ws_event(self, envelope: RawPayloadEnvelope) -> int:
        row = self._envelope_row(envelope)
        payload = envelope.payload if isinstance(envelope.payload, dict) else {}
        row["event_type"] = payload.get("event_type")
        sql = """
            INSERT INTO raw.websocket_events (
                source, endpoint, token_id, condition_id, event_type, payload,
                source_ts, received_at, collection_run_id, connection_id, gap_fill
            ) VALUES (
                %(source)s, %(endpoint)s, %(token_id)s, %(condition_id)s,
                %(event_type)s, %(payload)s, %(source_ts)s, %(received_at)s,
                %(collection_run_id)s, %(connection_id)s, %(gap_fill)s
            )
        """
        self._execute(sql, row)
        return 1

    def upsert_price_history_points(self, points: Sequence[PriceHistoryPoint]) -> int:
        rows = [point.model_dump(mode="json") for point in points]
        if not rows:
            return 0
        sql = """
            INSERT INTO normalized.price_history (
                token_id, condition_id, price, source_ts, received_at, source,
                collection_run_id, gap_fill
            ) VALUES (
                %(token_id)s, %(condition_id)s, %(price)s, %(source_ts)s,
                %(received_at)s, %(source)s, %(collection_run_id)s, %(gap_fill)s
            )
            ON CONFLICT (token_id, source_ts, source, gap_fill) DO UPDATE SET
                condition_id = EXCLUDED.condition_id,
                price = EXCLUDED.price,
                received_at = EXCLUDED.received_at,
                collection_run_id = EXCLUDED.collection_run_id
        """
        self._executemany(sql, rows)
        return len(rows)

    def insert_book_snapshot(self, snapshot: BookSnapshot) -> int:
        row = snapshot.model_dump(mode="json")
        row["book_hash"] = row.pop("hash")
        sql = """
            INSERT INTO normalized.book_snapshots (
                token_id, condition_id, market, source_ts, received_at, source,
                book_hash, min_order_size, tick_size, neg_risk, last_trade_price,
                collection_run_id, gap_fill
            ) VALUES (
                %(token_id)s, %(condition_id)s, %(market)s, %(source_ts)s,
                %(received_at)s, %(source)s, %(book_hash)s, %(min_order_size)s,
                %(tick_size)s, %(neg_risk)s, %(last_trade_price)s,
                %(collection_run_id)s, %(gap_fill)s
            )
            RETURNING id
        """
        with self._connect() as connection:
            result = connection.execute(sql, row)
            snapshot_id = self._scalar(result) or 0
            level_rows = [
                {
                    "snapshot_id": snapshot_id,
                    "token_id": snapshot.token_id,
                    "side": level.side,
                    "price": str(level.price),
                    "size": str(level.size),
                    "level_index": index,
                    "gap_fill": snapshot.gap_fill,
                }
                for index, level in enumerate([*snapshot.bids, *snapshot.asks])
            ]
            if level_rows:
                connection.executemany(
                    """
                    INSERT INTO normalized.book_levels (
                        snapshot_id, token_id, side, price, size, level_index, gap_fill
                    ) VALUES (
                        %(snapshot_id)s, %(token_id)s, %(side)s, %(price)s,
                        %(size)s, %(level_index)s, %(gap_fill)s
                    )
                    """,
                    level_rows,
                )
            self._commit(connection)
        return 1

    def upsert_best_bid_ask(self, rows: Sequence[BestBidAsk]) -> int:
        dumped = [row.model_dump(mode="json") for row in rows]
        if not dumped:
            return 0
        sql = """
            INSERT INTO normalized.best_bid_ask (
                token_id, condition_id, best_bid, best_ask, spread, midpoint,
                source_ts, received_at, source, collection_run_id, connection_id,
                gap_fill
            ) VALUES (
                %(token_id)s, %(condition_id)s, %(best_bid)s, %(best_ask)s,
                %(spread)s, %(midpoint)s, %(source_ts)s, %(received_at)s,
                %(source)s, %(collection_run_id)s, %(connection_id)s, %(gap_fill)s
            )
            ON CONFLICT (token_id) DO UPDATE SET
                condition_id = EXCLUDED.condition_id,
                best_bid = EXCLUDED.best_bid,
                best_ask = EXCLUDED.best_ask,
                spread = EXCLUDED.spread,
                midpoint = EXCLUDED.midpoint,
                source_ts = EXCLUDED.source_ts,
                received_at = EXCLUDED.received_at,
                source = EXCLUDED.source,
                collection_run_id = EXCLUDED.collection_run_id,
                connection_id = EXCLUDED.connection_id,
                gap_fill = EXCLUDED.gap_fill
        """
        self._executemany(sql, dumped)
        return len(dumped)

    def upsert_last_trades(self, rows: Sequence[LastTrade]) -> int:
        dumped = [row.model_dump(mode="json") for row in rows]
        if not dumped:
            return 0
        sql = """
            INSERT INTO normalized.last_trades (
                token_id, condition_id, price, side, size, source_ts, received_at,
                source, collection_run_id, connection_id, gap_fill
            ) VALUES (
                %(token_id)s, %(condition_id)s, %(price)s, %(side)s, %(size)s,
                %(source_ts)s, %(received_at)s, %(source)s, %(collection_run_id)s,
                %(connection_id)s, %(gap_fill)s
            )
            ON CONFLICT (token_id) DO UPDATE SET
                condition_id = EXCLUDED.condition_id,
                price = EXCLUDED.price,
                side = EXCLUDED.side,
                size = EXCLUDED.size,
                source_ts = EXCLUDED.source_ts,
                received_at = EXCLUDED.received_at,
                source = EXCLUDED.source,
                collection_run_id = EXCLUDED.collection_run_id,
                connection_id = EXCLUDED.connection_id,
                gap_fill = EXCLUDED.gap_fill
        """
        self._executemany(sql, dumped)
        return len(dumped)

    def record_gap_interval(self, interval: GapFillInterval) -> int:
        self._execute(
            """
            INSERT INTO raw.gap_fill_intervals (
                token_ids, gap_started_at, gap_ended_at, connection_id, reason, created_at
            ) VALUES (
                %(token_ids)s, %(gap_started_at)s, %(gap_ended_at)s,
                %(connection_id)s, %(reason)s, %(created_at)s
            )
            """,
            interval.model_dump(mode="json"),
        )
        return 1

    def fetch_latest_state(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._fetch_all(
            "SELECT * FROM views.latest_market_state ORDER BY received_at DESC NULLS LAST LIMIT %(limit)s",
            {"limit": limit},
        )

    def fetch_price_series(self, token_id: str, limit: int = 500) -> list[dict[str, Any]]:
        return self._fetch_all(
            """
            SELECT * FROM views.price_series_recent
            WHERE token_id = %(token_id)s
            ORDER BY source_ts DESC
            LIMIT %(limit)s
            """,
            {"token_id": token_id, "limit": limit},
        )

    def _connect(self) -> Any:
        if self.connection is not None:
            return _ConnectionContext(self.connection)
        if not self.dsn:
            raise ValueError("DATABASE_URL is required for MarketDataStore")
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
    def _scalar(result: Any) -> Any:
        fetchone = getattr(result, "fetchone", None)
        if not callable(fetchone):
            return None
        row = fetchone()
        if row is None:
            return None
        if isinstance(row, dict):
            return next(iter(row.values()))
        return row[0]

    @staticmethod
    def _adapt_params(params: dict[str, Any]) -> dict[str, Any]:
        adapted = dict(params)
        payload = adapted.get("payload")
        if payload is not None:
            try:
                from psycopg.types.json import Jsonb
            except ImportError:
                pass
            else:
                adapted["payload"] = Jsonb(payload)
        return adapted

    @staticmethod
    def _envelope_row(envelope: RawPayloadEnvelope) -> dict[str, Any]:
        return envelope.model_dump(mode="json")


class _ConnectionContext:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def __enter__(self) -> Any:
        return self.connection

    def __exit__(self, *_exc: object) -> None:
        return None
