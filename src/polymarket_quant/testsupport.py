from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from polymarket_quant.domain.strategy import ResolvedRunConfig, RunManifest, RunMode, UniverseSnapshot


def report_manifest(
    *,
    run_id: str,
    start_time: datetime,
    end_time: datetime,
) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        strategy_name="report-strategy",
        strategy_version="1.0.0",
        git_commit="deadbeef",
        start_time=start_time,
        end_time=end_time,
        mode=RunMode.REPLAY,
        environment="local",
        resolved_config=ResolvedRunConfig(
            strategy={"name": "report-strategy", "version": "1.0.0"},
            universe={},
            sizing={},
            execution={},
            risk={"cash_available": "1000"},
            data_sources={},
            mode=RunMode.REPLAY,
            replay={},
            realtime={},
        ),
        universe_snapshot=UniverseSnapshot(
            dataset_id="dataset-001",
            selection={"active": True},
            token_ids=["token-yes"],
            token_mappings=[
                {
                    "market_id": "market-1",
                    "event_id": "event-1",
                    "condition_id": "condition-1",
                    "token_id": "token-yes",
                }
            ],
            window_start=start_time,
            window_end=end_time,
        ),
        metrics_summary={
            "realized_pnl": Decimal("5"),
            "unrealized_pnl": Decimal("1"),
            "turnover": Decimal("10"),
            "max_drawdown": Decimal("2"),
            "exposure_peak": Decimal("8"),
        },
        created_at=datetime(2026, 4, 22, 8, 0, tzinfo=timezone.utc),
    )
