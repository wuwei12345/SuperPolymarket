from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from polymarket_quant.domain.market import CanonicalMarket, MarketSourceMap, SourceLabel
from polymarket_quant.services.dashboard_snapshot import DashboardSnapshotService
from polymarket_quant.services.market_display import MarketDisplayService
from polymarket_quant.services.operator_queries import OperatorQueryService
from polymarket_quant.services.run_artifacts import RunArtifactBundleWriter
from polymarket_quant.storage.market_store import MarketStore
from polymarket_quant.testsupport import report_manifest
from polymarket_quant.ui.operator_console_app import load_dashboard_snapshot


def instant() -> datetime:
    return datetime(2026, 4, 25, 8, 0, tzinfo=timezone.utc)


def test_dashboard_snapshot_writes_result_focused_latest_json(tmp_path: Path) -> None:
    artifact_root = tmp_path / "runs"
    market_store_path = tmp_path / "markets.sqlite3"
    MarketStore(market_store_path).upsert_markets(
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
                source_map=MarketSourceMap(
                    question=SourceLabel.GAMMA,
                    category=SourceLabel.GAMMA,
                    liquidity=SourceLabel.GAMMA,
                    end_date=SourceLabel.GAMMA,
                    condition_id=SourceLabel.NORMALIZED,
                    yes_token_id=SourceLabel.CLOB,
                    no_token_id=SourceLabel.CLOB,
                ),
                raw_gamma={
                    "outcomes": '["Yes","No"]',
                    "outcomePrices": '["0.55","0.45"]',
                    "volume24hr": "250",
                },
            )
        ]
    )
    manifest = report_manifest(run_id="run-snapshot", start_time=instant(), end_time=instant())
    RunArtifactBundleWriter(artifact_root).write_bundle(
        manifest,
        positions=[
            {
                "token_id": "token-yes",
                "quantity": "4",
                "avg_price": "0.50",
                "mark_price": "0.55",
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
        pnl_timeline=[
            {
                "ts": instant(),
                "total_pnl": "6",
                "equity": "1006",
                "drawdown": "1",
                "exposure": "2.2",
            }
        ],
        risk_decisions=[
            {
                "token_id": "token-yes",
                "decision": "WARN",
                "warnings": ["spread_warning"],
                "created_at": instant(),
            }
        ],
    )
    snapshot_path = tmp_path / "runtime" / "latest_snapshot.json"
    query_service = OperatorQueryService(artifact_root)
    service = DashboardSnapshotService(
        query_service,
        snapshot_path=snapshot_path,
        market_display_service=MarketDisplayService(
            market_store=MarketStore(market_store_path),
            query_service=query_service,
        ),
    )

    snapshot = service.write_latest(generated_at=instant())
    loaded = load_dashboard_snapshot(snapshot_path)

    assert snapshot_path.exists()
    assert loaded is not None
    assert loaded["schema_version"] == 1
    assert loaded["summary_cards"]["total_pnl"] == "6"
    assert loaded["curves"][0]["equity"] == "1006"
    assert loaded["current_positions"][0]["market"] == "market-1"
    assert loaded["recent_simulated_trades"][0]["amount"] == "2.00"
    assert loaded["market_cards"][0]["question"] == "Will it rain tomorrow?"
    assert loaded["market_cards"][0]["yes_probability_pct"] == "55.00"
    assert loaded["recent_simulated_trades_display"][0]["market_question"] == "Will it rain tomorrow?"
    assert snapshot["alert_summary"]["counts"]["Warning"] == 1
