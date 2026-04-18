from __future__ import annotations

from typing import Any, Protocol

import pandas as pd


LATEST_STATE_COLUMNS = [
    "question",
    "token_id",
    "outcome",
    "best_bid",
    "best_ask",
    "spread",
    "midpoint",
    "last_trade_price",
    "source",
    "gap_fill",
    "received_at",
]


class MarketDataStoreReader(Protocol):
    def fetch_latest_state(self, limit: int = 100) -> list[dict[str, Any]]: ...

    def fetch_price_series(
        self, token_id: str, limit: int = 500
    ) -> list[dict[str, Any]]: ...


class MarketDataQueryService:
    def __init__(self, store: MarketDataStoreReader) -> None:
        self.store = store

    def latest_state(self, limit: int = 100) -> list[dict[str, object]]:
        return self.store.fetch_latest_state(limit=limit)

    def price_series(self, token_id: str, limit: int = 500) -> list[dict[str, object]]:
        return self.store.fetch_price_series(token_id=token_id, limit=limit)

    def latest_state_dataframe(self, limit: int = 100) -> pd.DataFrame:
        return build_latest_state_dataframe(self.latest_state(limit=limit))

    def price_series_dataframe(
        self, token_id: str, limit: int = 500
    ) -> pd.DataFrame:
        return build_price_series_dataframe(
            self.price_series(token_id=token_id, limit=limit)
        )


def build_latest_state_dataframe(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows).reindex(columns=LATEST_STATE_COLUMNS)


def build_price_series_dataframe(rows: list[dict[str, object]]) -> pd.DataFrame:
    columns = [
        "token_id",
        "question",
        "outcome",
        "price",
        "source_ts",
        "received_at",
        "source",
        "gap_fill",
    ]
    return pd.DataFrame(rows).reindex(columns=columns)
