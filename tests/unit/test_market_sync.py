from __future__ import annotations

import httpx

from polymarket_quant.adapters.polymarket import (
    CLOB_BASE_URL,
    GAMMA_BASE_URL,
    USER_AGENT,
    ClobClient,
    GammaClient,
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
