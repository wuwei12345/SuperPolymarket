from __future__ import annotations

from datetime import datetime, timezone

import httpx

from polymarket_quant.adapters.polymarket import (
    CLOB_BASE_URL,
    GAMMA_BASE_URL,
    USER_AGENT,
    ClobClient,
    GammaClient,
)
from polymarket_quant.domain.market import SourceLabel
from polymarket_quant.services.market_sync import (
    MarketSyncService,
    SyncEvent,
    normalize_markets,
)
from polymarket_quant.storage.market_store import MarketStore


def test_gamma_client_fetches_active_open_markets() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[{"id": "gamma-1"}])

    client = GammaClient(client=httpx.Client(transport=httpx.MockTransport(handler)))

    markets = client.fetch_markets(limit=25, include_short_term=False)

    assert markets == [{"id": "gamma-1"}]
    assert requests[0].url == httpx.URL(
        f"{GAMMA_BASE_URL}/markets?active=true&closed=false&limit=25&offset=0"
    )
    assert requests[0].headers["user-agent"] == USER_AGENT


def test_gamma_client_fetches_short_term_end_date_page() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "order=endDate" in str(request.url):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "gamma-soon",
                        "conditionId": "condition-soon",
                        "endDate": "2026-05-06T12:00:00Z",
                    }
                ],
            )
        return httpx.Response(
            200,
            json=[{"id": "gamma-default", "conditionId": "condition-default"}],
        )

    client = GammaClient(client=httpx.Client(transport=httpx.MockTransport(handler)))

    markets = client.fetch_markets(
        limit=25,
        max_pages=1,
        include_short_term=True,
        short_term_pages=1,
    )

    assert [market["id"] for market in markets] == ["gamma-default", "gamma-soon"]
    assert "order=endDate" in str(requests[1].url)
    assert "ascending=true" in str(requests[1].url)
    assert "end_date_min=" in str(requests[1].url)


def test_clob_client_follows_next_cursor() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "data": [{"condition_id": "condition-1"}],
                    "next_cursor": "cursor-2",
                },
            )
        return httpx.Response(
            200,
            json={"data": [{"condition_id": "condition-2"}], "next_cursor": ""},
        )

    client = ClobClient(client=httpx.Client(transport=httpx.MockTransport(handler)))

    markets = client.fetch_simplified_markets(limit=2)

    assert markets == [{"condition_id": "condition-1"}, {"condition_id": "condition-2"}]
    assert requests[0].url == httpx.URL(f"{CLOB_BASE_URL}/simplified-markets?limit=2")
    assert requests[1].url == httpx.URL(
        f"{CLOB_BASE_URL}/simplified-markets?limit=2&next_cursor=cursor-2"
    )
    assert requests[0].headers["user-agent"] == USER_AGENT


def gamma_market(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "id": "gamma-1",
        "question": "Will normalization pass?",
        "category": "Testing",
        "liquidity": "1500.5",
        "endDate": "2099-06-01T00:00:00Z",
        "conditionId": "0x" + "a" * 64,
        "active": True,
        "closed": False,
        "acceptingOrders": True,
        "restricted": False,
        "clobTokenIds": '["gamma-yes", "gamma-no"]',
    }
    values.update(overrides)
    return values


def clob_market(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "condition_id": "0x" + "a" * 64,
        "active": True,
        "closed": False,
        "archived": False,
        "accepting_orders": True,
        "tokens": [
            {"outcome": "No", "token_id": "clob-no"},
            {"outcome": "Yes", "token_id": "clob-yes"},
        ],
    }
    values.update(overrides)
    return values


def test_normalize_keeps_only_active_accepting_markets() -> None:
    valid_condition = "0x" + "a" * 64
    inactive_condition = "0x" + "b" * 64
    non_accepting_condition = "0x" + "c" * 64

    markets, skipped = normalize_markets(
        [
            gamma_market(conditionId=valid_condition),
            gamma_market(id="gamma-2", conditionId=inactive_condition, active=False),
            gamma_market(id="gamma-3", conditionId=non_accepting_condition),
        ],
        [
            clob_market(condition_id=valid_condition),
            clob_market(condition_id=inactive_condition),
            clob_market(condition_id=non_accepting_condition, accepting_orders=False),
        ],
    )

    assert [market.condition_id for market in markets] == [valid_condition]
    assert len(skipped) == 2


def test_normalize_skips_markets_with_expired_end_date() -> None:
    expired_condition = "0x" + "d" * 64

    markets, skipped = normalize_markets(
        [
            gamma_market(
                conditionId=expired_condition,
                endDate="2025-01-01T00:00:00Z",
            )
        ],
        [clob_market(condition_id=expired_condition)],
    )

    assert markets == []
    assert skipped == [f"{expired_condition}: market end_date is already expired"]


def test_normalize_source_map_marks_gamma_and_clob_fields() -> None:
    markets, skipped = normalize_markets([gamma_market()], [clob_market()])

    assert skipped == []
    [market] = markets
    assert market.question == "Will normalization pass?"
    assert market.liquidity == 1500.5
    assert market.yes_token_id == "clob-yes"
    assert market.no_token_id == "clob-no"
    assert market.source_map.question is SourceLabel.GAMMA
    assert market.source_map.liquidity is SourceLabel.GAMMA
    assert market.source_map.condition_id is SourceLabel.NORMALIZED
    assert market.source_map.yes_token_id is SourceLabel.CLOB
    assert market.source_map.no_token_id is SourceLabel.CLOB


def test_normalize_uses_gamma_token_fallback_when_clob_match_missing() -> None:
    markets, skipped = normalize_markets([gamma_market()], [])

    assert skipped == []
    [market] = markets
    assert market.yes_token_id == "gamma-yes"
    assert market.no_token_id == "gamma-no"
    assert market.source_map.condition_id is SourceLabel.GAMMA
    assert market.source_map.yes_token_id is SourceLabel.GAMMA
    assert market.source_map.no_token_id is SourceLabel.GAMMA
    assert market.raw_clob is None


def test_sync_event_contract_exists() -> None:
    event = SyncEvent(
        timestamp=datetime.now(timezone.utc),
        step="Gamma fetch started",
        source="Gamma",
        status="started",
        message="Fetching Gamma markets",
    )

    assert event.source == "Gamma"


class FakeGammaClient:
    def __init__(self, markets: list[dict[str, object]] | None = None) -> None:
        self.markets = markets or []

    def fetch_markets(self, limit: int = 500) -> list[dict[str, object]]:
        return self.markets


class FakeClobClient:
    def __init__(self, markets: list[dict[str, object]] | None = None) -> None:
        self.markets = markets or []

    def fetch_simplified_markets(
        self, limit: int = 1000, max_pages: int = 20
    ) -> list[dict[str, object]]:
        return self.markets


class FailingGammaClient:
    def __init__(self) -> None:
        self.calls = 0

    def fetch_markets(self, limit: int = 500) -> list[dict[str, object]]:
        self.calls += 1
        raise RuntimeError("temporary Gamma outage")


def test_sync_writes_only_valid_markets_to_store(tmp_db_path) -> None:
    valid_condition = "0x" + "a" * 64
    invalid_condition = "0x" + "b" * 64
    service = MarketSyncService(
        gamma_client=FakeGammaClient(
            [
                gamma_market(conditionId=valid_condition),
                gamma_market(conditionId=invalid_condition),
            ]
        ),
        clob_client=FakeClobClient(
            [
                clob_market(condition_id=valid_condition),
                clob_market(condition_id=invalid_condition, accepting_orders=False),
            ]
        ),
        store=MarketStore(tmp_db_path),
    )

    result = service.sync_once()
    stored = MarketStore(tmp_db_path).list_markets()

    assert result.written_count == 1
    assert result.skipped_count == 1
    assert [market.condition_id for market in stored] == [valid_condition]
    assert [event.step for event in result.events] == [
        "Sync started",
        "Gamma fetch started",
        "Gamma fetch completed",
        "CLOB fetch started",
        "CLOB fetch completed",
        "Normalization completed",
        "Sync succeeded",
    ]


def test_sync_emits_retry_and_failure_events(tmp_db_path) -> None:
    gamma_client = FailingGammaClient()
    service = MarketSyncService(
        gamma_client=gamma_client,
        clob_client=FakeClobClient(),
        store=MarketStore(tmp_db_path),
        max_attempts=2,
    )

    result = service.sync_once()

    assert gamma_client.calls == 2
    assert result.written_count == 0
    assert result.errors == ["temporary Gamma outage"]
    assert [event.step for event in result.events] == [
        "Sync started",
        "Gamma fetch started",
        "Retry scheduled",
        "Gamma fetch started",
        "Retry failed",
        "Sync failed",
    ]
    assert any(
        "Retrying Gamma after request failure" in event.message
        for event in result.events
    )
