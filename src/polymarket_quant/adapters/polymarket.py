from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx


GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
CLOB_BASE_URL = "https://clob.polymarket.com"
DATA_BASE_URL = "https://data-api.polymarket.com"
USER_AGENT = "polymarket-quant-simulator/0.1"


class GammaClient:
    def __init__(
        self,
        client: httpx.Client | None = None,
        base_url: str = GAMMA_BASE_URL,
    ) -> None:
        self.client = client or httpx.Client()
        self.base_url = base_url.rstrip("/")

    def fetch_markets(
        self,
        limit: int = 500,
        *,
        max_pages: int = 5,
        include_short_term: bool = True,
        short_term_pages: int = 2,
    ) -> list[dict[str, Any]]:
        markets: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for page_params in self._market_page_params(
            limit=limit,
            max_pages=max_pages,
            include_short_term=include_short_term,
            short_term_pages=short_term_pages,
        ):
            page = self._fetch_market_page(page_params)
            self._append_unique_markets(markets, page, seen_keys)
        return markets

    def _fetch_market_page(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        response = self.client.get(
            f"{self.base_url}/markets",
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return payload
        return list(payload.get("data", []))

    def _market_page_params(
        self,
        *,
        limit: int,
        max_pages: int,
        include_short_term: bool,
        short_term_pages: int,
    ) -> list[dict[str, Any]]:
        base_params = {"active": "true", "closed": "false", "limit": limit}
        params = [
            {**base_params, "offset": page * limit}
            for page in range(max(1, max_pages))
        ]
        if include_short_term:
            end_date_min = _gamma_end_date_min()
            params.extend(
                {
                    **base_params,
                    "order": "endDate",
                    "ascending": "true",
                    "end_date_min": end_date_min,
                    "offset": page * limit,
                }
                for page in range(max(1, short_term_pages))
            )
        return params

    @staticmethod
    def _append_unique_markets(
        markets: list[dict[str, Any]],
        page: list[dict[str, Any]],
        seen_keys: set[str],
    ) -> None:
        for market in page:
            key = str(
                market.get("conditionId")
                or market.get("condition_id")
                or market.get("id")
                or market
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            markets.append(market)


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

    def fetch_prices_history_batch(
        self,
        markets: list[str],
        start_ts: int | None = None,
        end_ts: int | None = None,
        interval: str = "1d",
        fidelity: int = 1,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "markets": markets,
            "interval": interval,
            "fidelity": fidelity,
        }
        if start_ts is not None:
            payload["start_ts"] = start_ts
        if end_ts is not None:
            payload["end_ts"] = end_ts
        response = self.client.post(
            f"{self.base_url}/batch-prices-history",
            json=payload,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
        )
        response.raise_for_status()
        return dict(response.json())

    def fetch_order_books(self, token_ids: list[str]) -> list[dict[str, Any]]:
        response = self.client.post(
            f"{self.base_url}/books",
            json=[{"token_id": token_id} for token_id in token_ids],
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        return list(payload if isinstance(payload, list) else payload.get("data", []))

    def fetch_market_prices(
        self, params: list[dict[str, str]]
    ) -> dict[str, dict[str, float]]:
        response = self.client.post(
            f"{self.base_url}/prices",
            json=params,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
        )
        response.raise_for_status()
        return dict(response.json())

    def fetch_last_trade_prices(self, token_ids: list[str]) -> list[dict[str, Any]]:
        response = self.client.post(
            f"{self.base_url}/last-trades-prices",
            json=[{"token_id": token_id} for token_id in token_ids],
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        return list(payload if isinstance(payload, list) else payload.get("data", []))


class DataApiClient:
    def __init__(
        self,
        client: httpx.Client | None = None,
        base_url: str = DATA_BASE_URL,
    ) -> None:
        self.client = client or httpx.Client()
        self.base_url = base_url.rstrip("/")

    def fetch_trades(self, params: dict[str, object] | None = None) -> dict[str, Any]:
        return self._get_raw("/trades", params)

    def fetch_activity(self, params: dict[str, object] | None = None) -> dict[str, Any]:
        return self._get_raw("/activity", params)

    def _get_raw(
        self, endpoint: str, params: dict[str, object] | None = None
    ) -> dict[str, Any]:
        request_params = dict(params or {})
        request_params.setdefault("limit", 500)
        response = self.client.get(
            f"{self.base_url}{endpoint}",
            params=request_params,
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            return payload
        return {"data": payload}


def _gamma_end_date_min() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
