from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from polymarket_quant.services.dashboard_snapshot import DashboardSnapshotService
from polymarket_quant.services.operator_queries import OperatorQueryService
from polymarket_quant.services.run_artifacts import RunArtifactBundleWriter
from polymarket_quant.testsupport import report_manifest
from polymarket_quant.ui.operator_console_app import load_dashboard_snapshot


def instant() -> datetime:
    return datetime(2026, 4, 25, 8, 0, tzinfo=timezone.utc)


def test_dashboard_snapshot_writes_result_focused_latest_json(tmp_path: Path) -> None:
    artifact_root = tmp_path / "runs"
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
    service = DashboardSnapshotService(
        OperatorQueryService(artifact_root),
        snapshot_path=snapshot_path,
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
    assert snapshot["alert_summary"]["counts"]["Warning"] == 1
