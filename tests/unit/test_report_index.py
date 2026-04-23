from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from polymarket_quant.domain.automation import (
    AutomationResolvedConfig,
    AutomationRun,
    ReportFormat,
)
from polymarket_quant.domain.strategy import RunMode
from polymarket_quant.services.report_outputs import write_report_outputs


def automation_run(tmp_path: Path) -> AutomationRun:
    config = AutomationResolvedConfig(
        environment="local",
        mode=RunMode.REALTIME_PAPER,
        enabled_tasks=[],
        strategies=[],
        artifact_root=str(tmp_path / "runs"),
        automation_root=str(tmp_path / "automation"),
        report_output_dir=str(tmp_path / "reports"),
        market_store_path=str(tmp_path / "markets.sqlite3"),
        report_formats=[ReportFormat.MARKDOWN, ReportFormat.HTML],
        window_policy="calendar_yesterday",
        timezone="UTC",
    )
    return AutomationRun(
        run_id="automation-001",
        environment="local",
        mode=RunMode.REALTIME_PAPER,
        started_at=datetime(2026, 4, 22, 8, 0, tzinfo=timezone.utc),
        resolved_config=config,
    )


def test_report_outputs_write_markdown_and_html(tmp_path: Path) -> None:
    run = automation_run(tmp_path)

    reference = write_report_outputs(
        tmp_path / "reports",
        run,
        "# Daily Automation Report\n\n## Run Overview\n",
        report_formats=[ReportFormat.MARKDOWN, ReportFormat.HTML],
        window_start=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 4, 21, 23, 59, 59, tzinfo=timezone.utc),
    )

    assert Path(reference.markdown_path).exists()
    assert Path(reference.html_path).exists()


def test_report_index_tracks_run_and_output_paths(tmp_path: Path) -> None:
    run = automation_run(tmp_path)

    reference = write_report_outputs(
        tmp_path / "reports",
        run,
        "# Daily Automation Report\n",
        report_formats=[ReportFormat.MARKDOWN],
        window_start=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 4, 21, 23, 59, 59, tzinfo=timezone.utc),
    )

    lines = Path(reference.index_path).read_text().splitlines()
    entry = json.loads(lines[-1])
    assert entry["run_id"] == "automation-001"
    assert entry["markdown_path"] == reference.markdown_path


def test_html_output_preserves_core_sections(tmp_path: Path) -> None:
    run = automation_run(tmp_path)

    reference = write_report_outputs(
        tmp_path / "reports",
        run,
        "# Daily Automation Report\n\n## Run Overview\n\n## Runs / Artifacts\n",
        report_formats=[ReportFormat.MARKDOWN, ReportFormat.HTML],
        window_start=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 4, 21, 23, 59, 59, tzinfo=timezone.utc),
    )

    html = Path(reference.html_path).read_text()
    assert "Daily Automation Report" in html
    assert "Runs / Artifacts" in html
