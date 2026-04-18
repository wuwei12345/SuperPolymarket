from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from polymarket_quant.domain.market_data import (
    BestBidAsk,
    BookLevel,
    BookSnapshot,
    GapFillInterval,
    PriceHistoryPoint,
    RawPayloadEnvelope,
    ReferenceToken,
)
from polymarket_quant.storage.market_data_store import MarketDataStore


SCHEMA_PATH = Path("src/polymarket_quant/storage/postgres_schema.sql")


class FakeResult:
    def __init__(self, row: dict[str, object] | None = None) -> None:
        self.row = row or {"id": 1}

    def fetchone(self) -> dict[str, object]:
        return self.row

    def fetchall(self) -> list[dict[str, object]]:
        return [self.row]


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict[str, object] | None]] = []
        self.executed_many: list[tuple[str, list[dict[str, object]]]] = []
        self.commits = 0

    def execute(
        self, sql: str, params: dict[str, object] | None = None
    ) -> FakeResult:
        self.executed.append((sql, params))
        return FakeResult()

    def executemany(self, sql: str, rows: list[dict[str, object]]) -> None:
        self.executed_many.append((sql, rows))

    def commit(self) -> None:
        self.commits += 1


def instant() -> datetime:
    return datetime(2026, 4, 18, 9, 0, tzinfo=timezone.utc)


def reference_token(**overrides: object) -> ReferenceToken:
    values = {
        "token_id": "token-yes",
        "condition_id": "0xcondition",
        "market_id": "gamma-1",
        "question": "Will this plan pass?",
        "outcome": "Yes",
        "category": "Testing",
        "liquidity": Decimal("123.45"),
        "end_date": instant(),
        "universe_rank": 1,
        "selection_reason": "liquidity_desc_end_date_asc",
    }
    values.update(overrides)
    return ReferenceToken(**values)


def test_reference_token_rejects_blank_token_id() -> None:
    with pytest.raises(ValidationError):
        reference_token(token_id=" ")


def test_normalized_models_include_source_and_gap_fields() -> None:
    bbo = BestBidAsk(
        token_id="token-yes",
        condition_id="0xcondition",
        best_bid=Decimal("0.45"),
        best_ask=Decimal("0.50"),
        spread=Decimal("0.05"),
        midpoint=Decimal("0.475"),
        received_at=instant(),
        source_ts=instant(),
        gap_fill=True,
    )

    point = PriceHistoryPoint(
        token_id="token-yes",
        condition_id="0xcondition",
        price=Decimal("0.47"),
        received_at=instant(),
        source_ts=instant(),
    )

    assert bbo.source == "Normalized"
    assert bbo.gap_fill is True
    assert point.source == "CLOB_REST"
    assert point.gap_fill is False


def test_postgres_schema_defines_required_layers() -> None:
    schema = SCHEMA_PATH.read_text()

    assert "CREATE SCHEMA IF NOT EXISTS reference" in schema
    assert "CREATE SCHEMA IF NOT EXISTS raw" in schema
    assert "CREATE SCHEMA IF NOT EXISTS normalized" in schema
    assert "CREATE SCHEMA IF NOT EXISTS views" in schema
    assert "reference.tokens" in schema
    assert "raw.rest_payloads" in schema
    assert "raw.websocket_events" in schema
    assert "raw.gap_fill_intervals" in schema
    assert "normalized.price_history" in schema
    assert "normalized.book_snapshots" in schema
    assert "normalized.book_levels" in schema
    assert "normalized.best_bid_ask" in schema
    assert "normalized.last_trades" in schema
    assert "views.latest_market_state" in schema
    assert "views.price_series_recent" in schema
    assert "JSONB NOT NULL" in schema
    assert "gap_fill BOOLEAN NOT NULL DEFAULT false" in schema


def test_store_initializes_schema_from_sql_file() -> None:
    connection = FakeConnection()
    store = MarketDataStore(connection=connection)

    store.init_schema()

    assert connection.executed
    assert "CREATE SCHEMA IF NOT EXISTS reference" in connection.executed[0][0]
    assert connection.commits == 1


def test_store_inserts_raw_payload_before_normalized_records_contract() -> None:
    connection = FakeConnection()
    store = MarketDataStore(connection=connection)
    envelope = RawPayloadEnvelope(
        source="CLOB_REST",
        endpoint="/books",
        token_id="token-yes",
        condition_id="0xcondition",
        payload={"asset_id": "token-yes"},
        received_at=instant(),
    )
    bbo = BestBidAsk(
        token_id="token-yes",
        condition_id="0xcondition",
        best_bid=Decimal("0.45"),
        best_ask=Decimal("0.50"),
        spread=Decimal("0.05"),
        midpoint=Decimal("0.475"),
        received_at=instant(),
    )

    store.insert_raw_rest_payload(envelope)
    store.upsert_best_bid_ask([bbo])

    first_sql = connection.executed[0][0]
    second_sql = connection.executed_many[0][0]
    assert "INSERT INTO raw.rest_payloads" in first_sql
    assert "INSERT INTO normalized.best_bid_ask" in second_sql


def test_store_inserts_raw_ws_event_and_gap_interval() -> None:
    connection = FakeConnection()
    store = MarketDataStore(connection=connection)

    store.insert_raw_ws_event(
        RawPayloadEnvelope(
            source="CLOB_WS",
            endpoint="market",
            payload={"event_type": "best_bid_ask", "asset_id": "token-yes"},
            token_id="token-yes",
            received_at=instant(),
        )
    )
    store.record_gap_interval(
        GapFillInterval(
            token_ids=["token-yes"],
            gap_started_at=instant(),
            gap_ended_at=instant(),
            connection_id="conn-1",
            created_at=instant(),
        )
    )

    assert "INSERT INTO raw.websocket_events" in connection.executed[0][0]
    assert "event_type" in connection.executed[0][1]
    assert "INSERT INTO raw.gap_fill_intervals" in connection.executed[1][0]


def test_store_inserts_book_snapshot_with_levels() -> None:
    connection = FakeConnection()
    store = MarketDataStore(connection=connection)

    store.insert_book_snapshot(
        BookSnapshot(
            token_id="token-yes",
            condition_id="0xcondition",
            received_at=instant(),
            bids=[BookLevel(side="BUY", price=Decimal("0.45"), size=Decimal("10"))],
            asks=[BookLevel(side="SELL", price=Decimal("0.50"), size=Decimal("5"))],
        )
    )

    assert "INSERT INTO normalized.book_snapshots" in connection.executed[0][0]
    assert "INSERT INTO normalized.book_levels" in connection.executed_many[0][0]


def test_fetch_helpers_read_views() -> None:
    connection = FakeConnection()
    store = MarketDataStore(connection=connection)

    latest = store.fetch_latest_state(limit=1)
    series = store.fetch_price_series("token-yes", limit=1)

    assert latest == [{"id": 1}]
    assert series == [{"id": 1}]
    assert "views.latest_market_state" in connection.executed[0][0]
    assert "views.price_series_recent" in connection.executed[1][0]


def test_phase1_market_store_remains_sqlite_backed() -> None:
    market_store_source = Path("src/polymarket_quant/storage/market_store.py").read_text()
    market_data_store_source = Path(
        "src/polymarket_quant/storage/market_data_store.py"
    ).read_text()

    assert "sqlite3" in market_store_source
    assert "class MarketDataStore" in market_data_store_source
