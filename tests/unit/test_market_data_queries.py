from __future__ import annotations

from polymarket_quant.services.market_data_queries import MarketDataQueryService


class FakeStore:
    def fetch_latest_state(self, limit: int = 100) -> list[dict[str, object]]:
        return [
            {
                "question": "Will this market move?",
                "token_id": "token-a",
                "outcome": "Yes",
                "best_bid": 0.44,
                "best_ask": 0.46,
                "spread": 0.02,
                "midpoint": 0.45,
                "last_trade_price": 0.45,
                "source": "CLOB_WS",
                "gap_fill": False,
                "received_at": "2026-04-18T09:00:00Z",
            }
        ][:limit]

    def fetch_price_series(
        self, token_id: str, limit: int = 500
    ) -> list[dict[str, object]]:
        return [
            {
                "token_id": token_id,
                "question": "Will this market move?",
                "outcome": "Yes",
                "price": 0.45,
                "source_ts": "2026-04-18T09:00:00Z",
                "received_at": "2026-04-18T09:00:01Z",
                "source": "CLOB_REST",
                "gap_fill": True,
            }
        ][:limit]


def test_latest_state_dataframe_contains_required_columns() -> None:
    service = MarketDataQueryService(FakeStore())

    df = service.latest_state_dataframe()

    assert list(df.columns) == [
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
    assert df.loc[0, "source"] == "CLOB_WS"


def test_price_series_preserves_gap_fill_marker() -> None:
    service = MarketDataQueryService(FakeStore())

    df = service.price_series_dataframe("token-a")

    assert df.loc[0, "token_id"] == "token-a"
    assert bool(df.loc[0, "gap_fill"]) is True
    assert "source" in df.columns
