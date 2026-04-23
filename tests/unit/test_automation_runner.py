from __future__ import annotations

from pathlib import Path

from polymarket_quant.domain.automation import AutomationResolvedConfig, AutomationTaskName
from polymarket_quant.domain.strategy import RunMode
from polymarket_quant.services.automation_runner import AutomationRunner


def resolved_config(tmp_path: Path) -> AutomationResolvedConfig:
    return AutomationResolvedConfig(
        environment="local",
        mode=RunMode.REALTIME_PAPER,
        enabled_tasks=[
            AutomationTaskName.MARKET_SYNC,
            AutomationTaskName.REALTIME_HEALTH_CHECK,
            AutomationTaskName.STRATEGY_BATCH,
            AutomationTaskName.REPORT_GENERATION,
        ],
        strategies=[],
        artifact_root=str(tmp_path / "runs"),
        automation_root=str(tmp_path / "automation"),
        report_output_dir=str(tmp_path / "reports"),
        market_store_path=str(tmp_path / "markets.sqlite3"),
        report_formats=[],
        window_policy="calendar_yesterday",
        timezone="UTC",
    )


class DummyQueryService:
    def status_band(self, filters=None):
        return {
            "global_mode": "paper",
            "connections": [],
            "high_priority_alerts": 0,
            "last_updated": None,
        }

    def overview(self, group_by="strategy", filters=None):
        return []

    def pnl_exposure(self, filters=None):
        return []

    def pnl_exposure_for_run_ids(self, run_ids):
        return []

    def alerts_timeline(self, filters=None):
        return []

    def alerts_timeline_for_run_ids(self, run_ids):
        return []

    def runs_artifacts(self, filters=None):
        return []

    def runs_artifacts_for_run_ids(self, run_ids):
        return []


def test_strategy_batch_can_be_skipped_when_prerequisites_fail(tmp_path: Path) -> None:
    runner = AutomationRunner(
        sync_callable=lambda: {"written_count": 0, "skipped_count": 0, "errors": []},
        health_callable=lambda: {"ready_for_strategy": False, "global_mode": "paper", "connections": []},
        strategy_executor=lambda strategy: {"run_id": "run-1"},
        query_service_factory=lambda config: DummyQueryService(),
    )

    result = runner.run(resolved_config(tmp_path))
    strategy_batch = next(
        task for task in result.automation_run.task_results if task.task_name == AutomationTaskName.STRATEGY_BATCH
    )

    assert strategy_batch.status.value == "skipped"
    assert strategy_batch.details["reason"] == "prerequisites failed"


def test_runner_continues_after_health_failure_and_marks_report(tmp_path: Path) -> None:
    runner = AutomationRunner(
        sync_callable=lambda: {"written_count": 5, "skipped_count": 0, "errors": []},
        health_callable=lambda: {"ready_for_strategy": False, "global_mode": "paper", "connections": []},
        strategy_executor=lambda strategy: {"run_id": "run-1"},
        query_service_factory=lambda config: DummyQueryService(),
    )

    result = runner.run(resolved_config(tmp_path))

    assert result.report is not None
    health_task = next(
        task
        for task in result.automation_run.task_results
        if task.task_name == AutomationTaskName.REALTIME_HEALTH_CHECK
    )
    report_task = next(
        task
        for task in result.automation_run.task_results
        if task.task_name == AutomationTaskName.REPORT_GENERATION
    )
    assert health_task.status.value == "failed"
    assert report_task.status.value == "success"


def test_report_generation_is_always_attempted(tmp_path: Path) -> None:
    runner = AutomationRunner(
        sync_callable=lambda: (_ for _ in ()).throw(RuntimeError("sync down")),
        health_callable=lambda: {"ready_for_strategy": False, "global_mode": "paper", "connections": []},
        strategy_executor=lambda strategy: {"run_id": "run-1"},
        query_service_factory=lambda config: DummyQueryService(),
    )

    result = runner.run(resolved_config(tmp_path))

    assert any(
        task.task_name == AutomationTaskName.REPORT_GENERATION
        for task in result.automation_run.task_results
    )
