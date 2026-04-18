from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polymarket_quant.adapters.polymarket_ws import (
    MARKET_WS_URL,
    MarketWebSocketClient,
)
from polymarket_quant.domain.market_data import RawPayloadEnvelope, ReferenceToken
from polymarket_quant.services.realtime_collector import (
    GapFillService,
    MarketRealtimeCollector,
    SubscriptionPoolConfig,
    assign_subscription_pools,
)


def instant() -> datetime:
    return datetime(2026, 4, 18, 9, 0, tzinfo=timezone.utc)


def reference_token(token_id: str, rank: int = 1) -> ReferenceToken:
    return ReferenceToken(
        token_id=token_id,
        condition_id=f"condition-{token_id}",
        market_id=f"market-{token_id}",
        question=f"Question {token_id}",
        outcome="Yes",
        universe_rank=rank,
        selection_reason="liquidity_desc_end_date_asc",
    )


class FakeWebSocket:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self.messages = messages
        self.sent: list[str] = []

    async def __aenter__(self) -> "FakeWebSocket":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def send(self, message: str) -> None:
        self.sent.append(message)

    def __aiter__(self) -> "FakeWebSocket":
        self._index = 0
        return self

    async def __anext__(self) -> str:
        if self._index >= len(self.messages):
            raise StopAsyncIteration
        message = self.messages[self._index]
        self._index += 1
        return json.dumps(message)


class FakeWsClient:
    def __init__(self, messages: list[dict[str, Any]] | None = None) -> None:
        self.messages = messages or []
        self.subscribed: list[str] = []

    async def subscribe(self, token_ids: list[str]):
        self.subscribed = token_ids
        for message in self.messages:
            yield message


class FailingWsClient:
    async def subscribe(self, token_ids: list[str]):
        raise ConnectionError("socket dropped")
        yield {}


class FakeStore:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.raw_events: list[RawPayloadEnvelope] = []
        self.snapshots: list[object] = []
        self.bbo_rows: list[object] = []
        self.last_trades: list[object] = []
        self.gap_intervals: list[object] = []
        self.raw_rest_payloads: list[object] = []
        self.price_points: list[object] = []
        self.reference_tokens: list[object] = []

    def init_schema(self) -> None:
        self.calls.append("init_schema")

    def insert_raw_ws_event(self, envelope: RawPayloadEnvelope) -> int:
        self.calls.append("insert_raw_ws_event")
        self.raw_events.append(envelope)
        return 1

    def insert_book_snapshot(self, snapshot: object) -> int:
        self.calls.append("insert_book_snapshot")
        self.snapshots.append(snapshot)
        return 1

    def upsert_best_bid_ask(self, rows: list[object]) -> int:
        self.calls.append("upsert_best_bid_ask")
        self.bbo_rows.extend(rows)
        return len(rows)

    def upsert_last_trades(self, rows: list[object]) -> int:
        self.calls.append("upsert_last_trades")
        self.last_trades.extend(rows)
        return len(rows)

    def record_gap_interval(self, interval: object) -> int:
        self.calls.append("record_gap_interval")
        self.gap_intervals.append(interval)
        return 1

    def upsert_reference_tokens(self, tokens: list[object]) -> int:
        self.calls.append("upsert_reference_tokens")
        self.reference_tokens.extend(tokens)
        return len(tokens)

    def insert_raw_rest_payload(self, envelope: object) -> int:
        self.calls.append("insert_raw_rest_payload")
        self.raw_rest_payloads.append(envelope)
        return 1

    def upsert_price_history_points(self, points: list[object]) -> int:
        self.calls.append("upsert_price_history_points")
        self.price_points.extend(points)
        return len(points)

    def insert_book_snapshot_gap(self, snapshot: object) -> int:
        return self.insert_book_snapshot(snapshot)


class FakeClobClient:
    def fetch_prices_history_batch(
        self,
        markets: list[str],
        start_ts: int | None = None,
        end_ts: int | None = None,
        interval: str = "1d",
        fidelity: int = 1,
    ) -> dict[str, Any]:
        return {"history": {token_id: [{"t": 1_700_000_000, "p": "0.45"}] for token_id in markets}}

    def fetch_order_books(self, token_ids: list[str]) -> list[dict[str, Any]]:
        return [
            {
                "market": f"condition-{token_id}",
                "asset_id": token_id,
                "timestamp": "1700000000000",
                "bids": [{"price": "0.44", "size": "10"}],
                "asks": [{"price": "0.46", "size": "8"}],
                "last_trade_price": "0.45",
            }
            for token_id in token_ids
        ]


def test_market_ws_subscription_payload_uses_assets_ids_and_custom_feature() -> None:
    client = MarketWebSocketClient()

    payload = client.build_subscription_payload(["token-a", "token-b"])

    assert MARKET_WS_URL == "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    assert payload == {
        "assets_ids": ["token-a", "token-b"],
        "type": "market",
        "custom_feature_enabled": True,
    }


@pytest.mark.asyncio
async def test_market_ws_subscribe_sends_payload_and_yields_json() -> None:
    fake_ws = FakeWebSocket([{"event_type": "best_bid_ask", "asset_id": "token-a"}])
    client = MarketWebSocketClient(connector=lambda _url: fake_ws)

    messages = [message async for message in client.subscribe(["token-a"])]

    assert json.loads(fake_ws.sent[0])["assets_ids"] == ["token-a"]
    assert messages == [{"event_type": "best_bid_ask", "asset_id": "token-a"}]


@pytest.mark.asyncio
async def test_collector_persists_raw_ws_event_before_normalizing() -> None:
    store = FakeStore()
    collector = MarketRealtimeCollector(
        FakeWsClient(
            [
                {
                    "event_type": "best_bid_ask",
                    "asset_id": "token-a",
                    "market": "condition-token-a",
                    "best_bid": "0.44",
                    "best_ask": "0.46",
                    "spread": "0.02",
                    "timestamp": "1700000000000",
                }
            ]
        ),
        store,
        [reference_token("token-a")],
    )

    await collector.collect_once()

    assert store.calls.index("insert_raw_ws_event") < store.calls.index(
        "upsert_best_bid_ask"
    )
    assert store.raw_events[0].source == "CLOB_WS"


@pytest.mark.asyncio
async def test_collector_normalizes_best_bid_ask_and_last_trade() -> None:
    store = FakeStore()
    collector = MarketRealtimeCollector(
        FakeWsClient(
            [
                {
                    "event_type": "best_bid_ask",
                    "asset_id": "token-a",
                    "best_bid": "0.44",
                    "best_ask": "0.46",
                    "spread": "0.02",
                    "timestamp": "1700000000000",
                },
                {
                    "event_type": "last_trade_price",
                    "asset_id": "token-a",
                    "price": "0.45",
                    "side": "BUY",
                    "size": "3",
                    "timestamp": "1700000000001",
                },
            ]
        ),
        store,
        [reference_token("token-a")],
    )

    result = await collector.collect_once()

    assert result.normalized_count == 2
    assert store.bbo_rows[0].best_bid == Decimal("0.44")
    assert store.bbo_rows[0].best_ask == Decimal("0.46")
    assert store.last_trades[0].price == Decimal("0.45")


@pytest.mark.asyncio
async def test_collector_normalizes_book_price_change_and_tick_size_change() -> None:
    store = FakeStore()
    collector = MarketRealtimeCollector(
        FakeWsClient(
            [
                {
                    "event_type": "book",
                    "asset_id": "token-a",
                    "market": "condition-token-a",
                    "bids": [{"price": "0.44", "size": "2"}],
                    "asks": [{"price": "0.46", "size": "4"}],
                    "timestamp": "1700000000000",
                },
                {
                    "event_type": "price_change",
                    "market": "condition-token-a",
                    "timestamp": "1700000000001",
                    "price_changes": [
                        {
                            "asset_id": "token-a",
                            "best_bid": "0.43",
                            "best_ask": "0.47",
                        }
                    ],
                },
                {
                    "event_type": "tick_size_change",
                    "asset_id": "token-a",
                    "old_tick_size": "0.01",
                    "new_tick_size": "0.001",
                },
            ]
        ),
        store,
        [reference_token("token-a")],
    )

    result = await collector.collect_once()

    assert result.raw_event_count == 3
    assert store.snapshots
    assert len(store.bbo_rows) == 2
    assert any(event.step == "Tick size change captured" for event in result.events)


def test_subscription_pool_assigns_hot_warm_cold_by_rank() -> None:
    tokens = [reference_token(f"token-{index}", rank=index) for index in range(1, 7)]
    config = SubscriptionPoolConfig(hot_size=2, warm_size=2)

    pools = assign_subscription_pools(tokens, config)

    assert [token.token_id for token in pools.hot] == ["token-1", "token-2"]
    assert [token.token_id for token in pools.warm] == ["token-3", "token-4"]
    assert [token.token_id for token in pools.cold] == ["token-5", "token-6"]


def test_subscription_scheduler_keeps_hot_tokens_resident() -> None:
    tokens = [reference_token(f"token-{index}", rank=index) for index in range(1, 6)]
    pools = assign_subscription_pools(
        tokens,
        SubscriptionPoolConfig(
            hot_size=2,
            warm_size=2,
            warm_rotation_seconds=600,
            cold_sample_seconds=3600,
        ),
    )

    first = pools.next_subscription_batch(instant())
    second = pools.next_subscription_batch(instant() + timedelta(minutes=10))

    assert {"token-1", "token-2"}.issubset({token.token_id for token in first})
    assert {"token-1", "token-2"}.issubset({token.token_id for token in second})


@pytest.mark.asyncio
async def test_reconnect_records_gap_and_runs_gap_fill() -> None:
    store = FakeStore()
    gap_fill = GapFillService(FakeClobClient(), store, recent_history_minutes=60)
    collector = MarketRealtimeCollector(
        FailingWsClient(),
        store,
        [reference_token("token-a")],
        connection_id="conn-1",
        gap_fill_service=gap_fill,
    )

    result = await collector.collect_once()

    assert "record_gap_interval" in store.calls
    assert "insert_raw_rest_payload" in store.calls
    assert store.raw_rest_payloads[0].gap_fill is True
    assert any(event.step == "Gap fill completed" for event in result.events)


def test_realtime_readme_and_entrypoint_are_documented() -> None:
    readme = Path("README.md").read_text()
    source = Path("src/polymarket_quant/services/realtime_collector.py").read_text()

    assert "## Phase 2 Realtime Collector" in readme
    assert "python -m polymarket_quant.services.realtime_collector" in readme
    assert "recent_history_minutes: int = 60" in source
    assert "record_gap_interval" in source
    assert "gap_fill=True" in source
