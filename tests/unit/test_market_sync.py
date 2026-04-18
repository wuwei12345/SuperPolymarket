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
    SyncEvent,
    normalize_markets,
)


def test_gamma_client_fetches_active_open_markets() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[{"id": "gamma-1"}])

    client = GammaClient(client=httpx.Client(transport=httpx.MockTransport(handler)))

    markets = client.fetch_markets(limit=25)

    assert markets == [{"id": "gamma-1"}]
    assert requests[0].url == httpx.URL(
        f"{GAMMA_BASE_URL}/markets?active=true&closed=false&limit=25"
    )
    assert requests[0].headers["user-agent"] == USER_AGENT


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
        "endDate": "2026-06-01T00:00:00Z",
        "conditionId": "0x" + "a" * 64,
        "active": True,
        "closed": False,
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


def test_sync_event_contract_exists() -> None:
    event = SyncEvent(
        timestamp=datetime.now(timezone.utc),
        step="Gamma fetch started",
        source="Gamma",
        status="started",
        message="Fetching Gamma markets",
    )

    assert event.source == "Gamma"
