from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from polymarket_quant.domain.automation import (
    AutomationResolvedConfig,
    AutomationRun,
    AutomationTaskName,
    AutomationTaskResult,
    AutomationTaskStatus,
    ReportFormat,
)
from polymarket_quant.domain.strategy import RunMode
from polymarket_quant.services.automation_config import load_automation_config


def instant() -> datetime:
    return datetime(2026, 4, 22, 9, 0, tzinfo=timezone.utc)


def write_config(path: Path, *, enabled_tasks: list[str] | None = None) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "environment": "local",
                "mode": "realtime_paper",
                "enabled_tasks": enabled_tasks,
                "strategies": [
                    {
                        "name": "passive",
                        "strategy_class": "polymarket_quant.strategy.base:BaseStrategy",
                        "config_path": "strategy.daily.yaml",
                    }
                ],
                "artifact_root": "data/runs",
            }
        )
    )


def test_automation_run_serializes_resolved_config() -> None:
    resolved_config = AutomationResolvedConfig(
        environment="local",
        mode=RunMode.REALTIME_PAPER,
        enabled_tasks=[AutomationTaskName.MARKET_SYNC],
        strategies=[],
        artifact_root="/tmp/runs",
        automation_root="/tmp/automation",
        report_output_dir="/tmp/reports",
        market_store_path="/tmp/markets.sqlite3",
        report_formats=[ReportFormat.MARKDOWN],
        window_policy="calendar_yesterday",
        timezone="UTC",
    )
    automation_run = AutomationRun(
        run_id="automation-001",
        environment="local",
        mode=RunMode.REALTIME_PAPER,
        started_at=instant(),
        resolved_config=resolved_config,
    )

    payload = automation_run.model_dump(mode="json")

    assert payload["resolved_config"]["mode"] == "realtime_paper"
    assert payload["resolved_config"]["enabled_tasks"] == ["market_sync"]


def test_task_result_distinguishes_failed_and_skipped() -> None:
    failed = AutomationTaskResult(
        task_name=AutomationTaskName.REPORT_GENERATION,
        status=AutomationTaskStatus.FAILED,
        started_at=instant(),
        ended_at=instant(),
        message="report generation failed",
    )
    skipped = AutomationTaskResult(
        task_name=AutomationTaskName.STRATEGY_BATCH,
        status=AutomationTaskStatus.SKIPPED,
        started_at=instant(),
        ended_at=instant(),
        message="strategy batch skipped",
    )

    assert failed.status == AutomationTaskStatus.FAILED
    assert skipped.status == AutomationTaskStatus.SKIPPED
    assert failed.status != skipped.status


def test_config_loader_applies_phase6_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "automation.yaml"
    strategy_config = tmp_path / "strategy.daily.yaml"
    strategy_config.write_text("mode: realtime_paper\n")
    write_config(config_path)

    resolved = load_automation_config(config_path)

    assert resolved.mode == RunMode.REALTIME_PAPER
    assert resolved.enabled_tasks == [
        AutomationTaskName.MARKET_SYNC,
        AutomationTaskName.REALTIME_HEALTH_CHECK,
        AutomationTaskName.STRATEGY_BATCH,
        AutomationTaskName.REPORT_GENERATION,
    ]
    assert resolved.report_formats == [ReportFormat.MARKDOWN, ReportFormat.HTML]
    assert resolved.strategies[0].config_path == str(strategy_config.resolve())


def test_config_loader_resolves_output_paths_from_workspace_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace_root = tmp_path / "workspace"
    config_dir = workspace_root / "config"
    config_dir.mkdir(parents=True)
    monkeypatch.chdir(workspace_root)
    config_path = config_dir / "automation.yaml"
    strategy_config = config_dir / "strategy.daily.yaml"
    strategy_config.write_text("mode: realtime_paper\n")
    write_config(config_path)

    resolved = load_automation_config(config_path)

    assert resolved.artifact_root == str((workspace_root / "data/runs").resolve())
    assert resolved.automation_root == str((workspace_root / "data/automation").resolve())
    assert resolved.report_output_dir == str(
        (workspace_root / "data/reports/daily").resolve()
    )
    assert resolved.strategies[0].config_path == str(strategy_config.resolve())


def test_config_loader_rejects_unknown_default_tasks(tmp_path: Path) -> None:
    config_path = tmp_path / "bad-automation.yaml"
    write_config(config_path, enabled_tasks=["market_sync", "not_a_task"])

    with pytest.raises(ValueError):
        load_automation_config(config_path)
