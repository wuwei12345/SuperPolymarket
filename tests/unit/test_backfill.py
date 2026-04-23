from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from polymarket_quant.adapters.polymarket import ClobClient, DataApiClient
from polymarket_quant.domain.market import CanonicalMarket, MarketSourceMap, SourceLabel
from polymarket_quant.domain.market_data import RawPayloadEnvelope, ReferenceToken
from polymarket_quant.services import StrategyCliService
from polymarket_quant.services.backfill import MarketDataBackfillService, main
from polymarket_quant.services.universe_selector import UniverseSelector


def source_map() -> MarketSourceMap:
    return MarketSourceMap(
        question=SourceLabel.GAMMA,
        category=SourceLabel.GAMMA,
        liquidity=SourceLabel.GAMMA,
        end_date=SourceLabel.GAMMA,
        condition_id=SourceLabel.NORMALIZED,
        yes_token_id=SourceLabel.GAMMA,
        no_token_id=SourceLabel.GAMMA,
    )


def market(**overrides: object) -> CanonicalMarket:
    values = {
        "market_id": "market-1",
        "question": "Will token one trade?",
        "category": "Crypto",
        "liquidity": 1000.0,
        "end_date": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "condition_id": "0xcondition1",
        "yes_token_id": "token-yes-1",
        "no_token_id": "token-no-1",
        "active": True,
        "accepting_orders": True,
        "restricted": False,
        "source_map": source_map(),
    }
    values.update(overrides)
    return CanonicalMarket(**values)


class FakeMarketStore:
    def __init__(self, markets: list[CanonicalMarket]) -> None:
        self.markets = markets

    def list_markets(self) -> list[CanonicalMarket]:
        return self.markets


class FakeSelector:
    def __init__(self, tokens: list[ReferenceToken]) -> None:
        self.tokens = tokens

    def select_top_tokens(self) -> list[ReferenceToken]:
        return self.tokens


class FakeClobBackfillClient:
    def __init__(self) -> None:
        self.history_calls: list[list[str]] = []
        self.book_calls: list[list[str]] = []

    def fetch_prices_history_batch(
        self,
        markets: list[str],
        start_ts: int | None = None,
        end_ts: int | None = None,
        interval: str = "1d",
        fidelity: int = 1,
    ) -> dict[str, Any]:
        self.history_calls.append(markets)
        return {
            "history": {
                token_id: [{"t": 1_700_000_000, "p": "0.45"}] for token_id in markets
            }
        }

    def fetch_order_books(self, token_ids: list[str]) -> list[dict[str, Any]]:
        self.book_calls.append(token_ids)
        return [
            {
                "market": "0xcondition1",
                "asset_id": token_id,
                "timestamp": "1700000000000",
                "hash": "0xbook",
                "bids": [{"price": "0.45", "size": "10"}],
                "asks": [{"price": "0.50", "size": "5"}],
                "min_order_size": "1",
                "tick_size": "0.01",
                "neg_risk": False,
                "last_trade_price": "0.47",
            }
            for token_id in token_ids
        ]


class FakeMarketDataStore:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.raw_payloads: list[RawPayloadEnvelope] = []
        self.reference_tokens: list[ReferenceToken] = []
        self.price_points: list[object] = []
        self.snapshots: list[object] = []
        self.bbo_rows: list[object] = []
        self.last_trades: list[object] = []

    def init_schema(self) -> None:
        self.calls.append("init_schema")

    def upsert_reference_tokens(self, tokens: list[ReferenceToken]) -> int:
        self.calls.append("upsert_reference_tokens")
        self.reference_tokens.extend(tokens)
        return len(tokens)

    def insert_raw_rest_payload(self, envelope: RawPayloadEnvelope) -> int:
        self.calls.append(f"raw:{envelope.endpoint}")
        self.raw_payloads.append(envelope)
        return 1

    def upsert_price_history_points(self, points: list[object]) -> int:
        self.calls.append("upsert_price_history_points")
        self.price_points.extend(points)
        return len(points)

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


def reference_token(token_id: str, rank: int = 1) -> ReferenceToken:
    return ReferenceToken(
        token_id=token_id,
        condition_id="0xcondition1",
        market_id="market-1",
        question="Will token one trade?",
        outcome="Yes",
        liquidity=Decimal("1000"),
        universe_rank=rank,
        selection_reason="liquidity_desc_end_date_asc",
    )


def test_clob_client_posts_batch_prices_history() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"history": {"token-a": []}})

    client = ClobClient(client=httpx.Client(transport=httpx.MockTransport(handler)))

    payload = client.fetch_prices_history_batch(["token-a"], interval="1d", fidelity=1)

    assert seen["url"] == "https://clob.polymarket.com/batch-prices-history"
    assert seen["body"] == {
        "markets": ["token-a"],
        "interval": "1d",
        "fidelity": 1,
    }
    assert payload == {"history": {"token-a": []}}


def test_clob_client_fetches_books_prices_and_last_trades() -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        if request.url.path == "/prices":
            return httpx.Response(200, json={"token-a": {"BUY": 0.45}})
        return httpx.Response(200, json=[])

    client = ClobClient(client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert client.fetch_order_books(["token-a"]) == []
    assert client.fetch_market_prices([{"token_id": "token-a", "side": "BUY"}]) == {
        "token-a": {"BUY": 0.45}
    }
    assert client.fetch_last_trade_prices(["token-a"]) == []
    assert urls == [
        "https://clob.polymarket.com/books",
        "https://clob.polymarket.com/prices",
        "https://clob.polymarket.com/last-trades-prices",
    ]


def test_data_api_client_fetches_trades_as_raw_optional_payload() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json=[{"id": "trade-1"}])

    client = DataApiClient(client=httpx.Client(transport=httpx.MockTransport(handler)))

    payload = client.fetch_trades({"user": "0xabc"})

    assert seen["url"] == "https://data-api.polymarket.com/trades?user=0xabc&limit=500"
    assert payload == {"data": [{"id": "trade-1"}]}


def test_universe_selector_ranks_active_accepting_tokens_by_liquidity() -> None:
    selector = UniverseSelector(
        FakeMarketStore(
            [
                market(
                    question="Low liquidity",
                    liquidity=10,
                    yes_token_id="low-yes",
                    no_token_id="low-no",
                ),
                market(
                    question="High liquidity",
                    liquidity=1000,
                    yes_token_id="high-yes",
                    no_token_id="high-no",
                ),
            ]
        ),
        top_n=4,
    )

    tokens = selector.select_top_tokens()

    assert [token.token_id for token in tokens] == [
        "high-yes",
        "high-no",
        "low-yes",
        "low-no",
    ]
    assert tokens[0].selection_reason == "liquidity_desc_end_date_asc"


def test_universe_selector_limits_by_token_count_not_market_count() -> None:
    selector = UniverseSelector(
        FakeMarketStore([market(yes_token_id="yes-a", no_token_id="no-a")]),
        top_n=1,
    )

    tokens = selector.select_top_tokens()

    assert [token.token_id for token in tokens] == ["yes-a"]


def test_backfill_writes_raw_price_history_before_normalized_points() -> None:
    store = FakeMarketDataStore()
    service = MarketDataBackfillService(
        FakeSelector([reference_token("token-a")]),
        FakeClobBackfillClient(),
        store,
    )

    service.backfill_top_tokens()

    assert store.calls.index("raw:/batch-prices-history") < store.calls.index(
        "upsert_price_history_points"
    )
    assert len(store.price_points) == 1


def test_backfill_fetches_book_snapshot_after_price_history() -> None:
    store = FakeMarketDataStore()
    clob_client = FakeClobBackfillClient()
    service = MarketDataBackfillService(
        FakeSelector([reference_token("token-a")]),
        clob_client,
        store,
    )

    result = service.backfill_top_tokens()

    assert clob_client.history_calls == [["token-a"]]
    assert clob_client.book_calls == [["token-a"]]
    assert store.calls.index("upsert_price_history_points") < store.calls.index(
        "raw:/books"
    )
    assert result.book_snapshot_count == 1


def test_backfill_derives_spread_and_midpoint_from_book() -> None:
    store = FakeMarketDataStore()
    service = MarketDataBackfillService(
        FakeSelector([reference_token("token-a")]),
        FakeClobBackfillClient(),
        store,
    )

    result = service.backfill_top_tokens()

    assert result.best_bid_ask_count == 1
    [bbo] = store.bbo_rows
    assert bbo.best_bid == Decimal("0.45")
    assert bbo.best_ask == Decimal("0.50")
    assert bbo.spread == Decimal("0.05")
    assert bbo.midpoint == Decimal("0.475")
    assert store.last_trades[0].price == Decimal("0.47")


def test_backfill_marks_gap_fill_records() -> None:
    store = FakeMarketDataStore()
    service = MarketDataBackfillService(
        FakeSelector([reference_token("token-a")]),
        FakeClobBackfillClient(),
        store,
    )

    service.backfill_top_tokens(gap_fill=True)

    assert all(payload.gap_fill for payload in store.raw_payloads)
    assert store.price_points[0].gap_fill is True
    assert store.bbo_rows[0].gap_fill is True


def test_readme_documents_phase2_backfill_command() -> None:
    readme = Path("README.md").read_text()
    backfill_source = Path("src/polymarket_quant/services/backfill.py").read_text()

    assert "## Phase 2 REST Backfill" in readme
    assert "POLYMARKET_TOP_N=50" in readme
    assert "python -m polymarket_quant.services.backfill" in readme
    assert 'if __name__ == "__main__":' in backfill_source


def test_backfill_main_requires_database_url_and_prints_actionable_error(
    capsys, monkeypatch
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "backfill requires PostgreSQL" in captured.err
    assert "DATABASE_URL" in captured.err


def test_services_package_uses_lazy_exports() -> None:
    assert StrategyCliService.__name__ == "StrategyCliService"
