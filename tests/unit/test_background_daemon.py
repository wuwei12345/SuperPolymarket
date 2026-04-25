from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from polymarket_quant.domain.automation import (
    AutomationResolvedConfig,
    AutomationRun,
    AutomationTaskName,
    ReportFormat,
    ReportReference,
)
from polymarket_quant.domain.strategy import RunMode
from polymarket_quant.services.automation_runner import AutomationRunResult
from polymarket_quant.services.background_daemon import (
    BackgroundDaemonService,
    DaemonResolvedConfig,
    DaemonTaskSchedule,
    load_daemon_config,
)
from polymarket_quant.services.runtime_state_store import RuntimeStateStore


def instant() -> datetime:
    return datetime(2026, 4, 25, 8, 0, tzinfo=timezone.utc)


def automation_config(tmp_path: Path) -> AutomationResolvedConfig:
    return AutomationResolvedConfig(
        environment="local",
        mode=RunMode.REALTIME_PAPER,
        enabled_tasks=[],
        strategies=[],
        artifact_root=str(tmp_path / "runs"),
        automation_root=str(tmp_path / "automation"),
        report_output_dir=str(tmp_path / "reports"),
        market_store_path=str(tmp_path / "markets.sqlite3"),
        report_formats=[ReportFormat.MARKDOWN, ReportFormat.HTML],
    )


def automation_result(tmp_path: Path) -> AutomationRunResult:
    run = AutomationRun(
        run_id="automation-daemon-001",
        environment="local",
        mode=RunMode.REALTIME_PAPER,
        started_at=instant(),
        ended_at=instant() + timedelta(seconds=1),
        resolved_config=automation_config(tmp_path),
        report=ReportReference(
            window_start=instant() - timedelta(days=1),
            window_end=instant(),
            markdown_path=str(tmp_path / "reports" / "daily.md"),
            html_path=str(tmp_path / "reports" / "daily.html"),
        ),
    )
    return AutomationRunResult(run, tmp_path / "automation" / run.run_id)


def test_runtime_state_store_tracks_heartbeat_task_error_and_stop(tmp_path: Path) -> None:
    store = RuntimeStateStore(tmp_path / "runtime" / "daemon_state.json")

    store.heartbeat(at=instant())
    store.start_task("strategy_batch", at=instant())
    store.fail_task("strategy_batch", "boom", at=instant() + timedelta(seconds=1))
    state = store.request_stop()

    assert state.stop_requested is True
    assert store.should_stop() is True
    assert store.load().heartbeat_at == instant() + timedelta(seconds=1)
    assert store.load().recent_error == "boom"
    assert store.load().tasks["strategy_batch"].last_status == "failed"


def test_background_daemon_runs_due_tasks_once_and_updates_state(tmp_path: Path) -> None:
    calls: list[list[AutomationTaskName]] = []
    store = RuntimeStateStore(tmp_path / "runtime" / "daemon_state.json")
    config = DaemonResolvedConfig(
        automation_config_path=str(tmp_path / "automation.yaml"),
        runtime_root=str(tmp_path / "runtime"),
        poll_interval_seconds=1,
        tasks=[
            DaemonTaskSchedule(
                task_name=AutomationTaskName.MARKET_SYNC,
                interval_seconds=60,
            ),
            DaemonTaskSchedule(
                task_name=AutomationTaskName.STRATEGY_BATCH,
                interval_seconds=120,
            ),
        ],
    )
    service = BackgroundDaemonService(
        config,
        state_store=store,
        run_callable=lambda tasks: calls.append(tasks) or automation_result(tmp_path),
        now=instant,
        sleep=lambda _seconds: None,
    )

    due_tasks = service.run_due_once()
    state = store.load()

    assert due_tasks == [AutomationTaskName.MARKET_SYNC, AutomationTaskName.STRATEGY_BATCH]
    assert calls == [due_tasks]
    assert state.recent_run_id == "automation-daemon-001"
    assert state.recent_report_path.endswith("daily.html")
    assert state.tasks["market_sync"].next_run_at == instant() + timedelta(seconds=60)
    assert state.tasks["strategy_batch"].next_run_at == instant() + timedelta(seconds=120)


def test_load_daemon_config_resolves_aliases_and_paths(tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "daemon.local.yaml"
    config_path.parent.mkdir()
    config_path.write_text(
        "\n".join(
            [
                "automation_config_path: automation.daily.yaml",
                "runtime_root: data/runtime",
                "poll_interval_seconds: 5",
                "tasks:",
                "  health_check:",
                "    interval_seconds: 30",
                "  daily_report:",
                "    enabled: false",
                "    interval_seconds: 86400",
            ]
        )
    )
    (config_path.parent / "automation.daily.yaml").write_text("{}")

    config = load_daemon_config(config_path)

    assert config.automation_config_path == str((config_path.parent / "automation.daily.yaml").resolve())
    assert config.poll_interval_seconds == 5
    assert config.tasks[0].task_name == AutomationTaskName.REALTIME_HEALTH_CHECK
    assert config.tasks[1].task_name == AutomationTaskName.REPORT_GENERATION
    assert config.tasks[1].enabled is False
