from __future__ import annotations

from typing import Any

import httpx


GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
CLOB_BASE_URL = "https://clob.polymarket.com"
USER_AGENT = "polymarket-quant-simulator/0.1"


class GammaClient:
    def __init__(
        self,
        client: httpx.Client | None = None,
        base_url: str = GAMMA_BASE_URL,
    ) -> None:
        self.client = client or httpx.Client()
        self.base_url = base_url.rstrip("/")

    def fetch_markets(self, limit: int = 500) -> list[dict[str, Any]]:
        response = self.client.get(
            f"{self.base_url}/markets",
            params={"active": "true", "closed": "false", "limit": limit},
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        return list(payload.get("data", []))


class ClobClient:
    def __init__(
        self,
        client: httpx.Client | None = None,
        base_url: str = CLOB_BASE_URL,
    ) -> None:
        self.client = client or httpx.Client()
        self.base_url = base_url.rstrip("/")

    def fetch_simplified_markets(
        self,
        limit: int = 1000,
        max_pages: int = 20,
    ) -> list[dict[str, Any]]:
        markets: list[dict[str, Any]] = []
        next_cursor: str | None = None

        for _ in range(max_pages):
            params: dict[str, object] = {"limit": limit}
            if next_cursor:
                params["next_cursor"] = next_cursor

            response = self.client.get(
                f"{self.base_url}/simplified-markets",
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=30.0,
            )
            response.raise_for_status()
            payload = response.json()

            if isinstance(payload, list):
                markets.extend(payload)
                break

            markets.extend(payload.get("data", []))
            cursor = payload.get("next_cursor")
            if not cursor or cursor == next_cursor:
                break
            next_cursor = cursor

        return markets
