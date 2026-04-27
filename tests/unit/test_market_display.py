from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from polymarket_quant.domain.market import CanonicalMarket, MarketSourceMap, SourceLabel
from polymarket_quant.services.market_display import MarketDisplayService
from polymarket_quant.services.operator_queries import OperatorQueryService
from polymarket_quant.services.run_artifacts import RunArtifactBundleWriter
from polymarket_quant.storage.market_store import MarketStore
from polymarket_quant.testsupport import report_manifest


class FakeLatestMarketDataStore:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetch_latest_state(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.rows[:limit]


def instant() -> datetime:
    return datetime(2026, 4, 25, 8, 0, tzinfo=timezone.utc)


def source_map() -> MarketSourceMap:
    return MarketSourceMap(
        question=SourceLabel.GAMMA,
        category=SourceLabel.GAMMA,
        liquidity=SourceLabel.GAMMA,
        end_date=SourceLabel.GAMMA,
        condition_id=SourceLabel.NORMALIZED,
        yes_token_id=SourceLabel.CLOB,
        no_token_id=SourceLabel.CLOB,
    )


def write_market(store_path: Path) -> None:
    MarketStore(store_path).upsert_markets(
        [
            CanonicalMarket(
                market_id="market-1",
                question="Will it rain tomorrow?",
                category="Weather",
                liquidity=1000.0,
                end_date=instant(),
                condition_id="condition-1",
                yes_token_id="token-yes",
                no_token_id="token-no",
                active=True,
                accepting_orders=True,
                source_map=source_map(),
                raw_gamma={
                    "volume": "5000",
                    "volume24hr": "250",
                    "outcomes": '["Yes","No"]',
                    "outcomePrices": '["0.54","0.46"]',
                },
            )
        ]
    )


def write_strategy_artifacts(artifact_root: Path) -> None:
    manifest = report_manifest(run_id="run-display", start_time=instant(), end_time=instant())
    RunArtifactBundleWriter(artifact_root).write_bundle(
        manifest,
        signals=[
            {
                "token_id": "token-yes",
                "reason_code": "bootstrap_enter",
                "target_exposure": "0.05",
            }
        ],
        order_intents=[
            {
                "client_order_id": "order-1",
                "token_id": "token-yes",
                "reason_code": "bootstrap_enter",
            }
        ],
        fills=[
            {
                "client_order_id": "order-1",
                "token_id": "token-yes",
                "side": "BUY",
                "price": "0.50",
                "size": "4",
                "created_at": instant(),
            }
        ],
        positions=[
            {
                "token_id": "token-yes",
                "quantity": "4",
                "avg_price": "0.50",
                "mark_price": "0.55",
                "pnl": "0.20",
            }
        ],
    )


def test_market_display_cards_join_market_prices_positions_and_reason_code(
    tmp_path: Path,
) -> None:
    market_store_path = tmp_path / "markets.sqlite3"
    artifact_root = tmp_path / "runs"
    write_market(market_store_path)
    write_strategy_artifacts(artifact_root)
    service = MarketDisplayService(
        market_store=MarketStore(market_store_path),
        query_service=OperatorQueryService(artifact_root),
        market_data_store=FakeLatestMarketDataStore(
            [
                {
                    "token_id": "token-yes",
                    "outcome": "Yes",
                    "midpoint": Decimal("0.55"),
                    "spread": Decimal("0.02"),
                    "last_trade_price": Decimal("0.56"),
                },
                {
                    "token_id": "token-no",
                    "outcome": "No",
                    "midpoint": Decimal("0.45"),
                    "spread": Decimal("0.02"),
                    "last_trade_price": Decimal("0.44"),
                },
            ]
        ),
    )

    cards = service.market_cards()
    trades = service.recent_trades()

    assert cards[0]["question"] == "Will it rain tomorrow?"
    assert cards[0]["yes_probability_pct"] == Decimal("55.00")
    assert cards[0]["no_probability_pct"] == Decimal("45.00")
    assert cards[0]["position_side"] == "YES"
    assert cards[0]["current_value"] == Decimal("2.20")
    assert cards[0]["pnl_pct"] == Decimal("10.0")
    assert cards[0]["last_signal_reason"] == "bootstrap_enter"
    assert cards[0]["volume_24h"] == Decimal("250")
    assert trades[0]["market_question"] == "Will it rain tomorrow?"
    assert trades[0]["action"] == "enter"
    assert trades[0]["side"] == "YES"
    assert trades[0]["notional"] == Decimal("2.00")


def test_market_display_falls_back_to_gamma_prices_without_market_data(
    tmp_path: Path,
) -> None:
    market_store_path = tmp_path / "markets.sqlite3"
    write_market(market_store_path)

    cards = MarketDisplayService(
        market_store=MarketStore(market_store_path),
        query_service=OperatorQueryService(tmp_path / "runs"),
    ).market_cards()

    assert cards[0]["yes_price"] == Decimal("0.54")
    assert cards[0]["no_price"] == Decimal("0.46")
    assert cards[0]["volume"] == Decimal("5000")
