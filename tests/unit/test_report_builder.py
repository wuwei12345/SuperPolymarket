from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from polymarket_quant.domain.automation import (
    AutomationResolvedConfig,
    AutomationRun,
    AutomationTaskName,
    AutomationTaskResult,
    AutomationTaskStatus,
)
from polymarket_quant.domain.strategy import RunMode
from polymarket_quant.services.operator_queries import OperatorQueryService
from polymarket_quant.services.report_builder import ReportBuilder
from polymarket_quant.services.run_artifacts import RunArtifactBundleWriter
from polymarket_quant.testsupport import report_manifest


def instant() -> datetime:
    return datetime(2026, 4, 22, 8, 0, tzinfo=timezone.utc)


def automation_run(tmp_path: Path) -> AutomationRun:
    config = AutomationResolvedConfig(
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
    return AutomationRun(
        run_id="automation-001",
        environment="local",
        mode=RunMode.REALTIME_PAPER,
        started_at=instant(),
        resolved_config=config,
        task_results=[
            AutomationTaskResult(
                task_name=AutomationTaskName.MARKET_SYNC,
                status=AutomationTaskStatus.SUCCESS,
                started_at=instant(),
                ended_at=instant(),
                message="market sync completed",
                details={"written_count": 5, "skipped_count": 1, "errors": []},
            ),
            AutomationTaskResult(
                task_name=AutomationTaskName.REALTIME_HEALTH_CHECK,
                status=AutomationTaskStatus.FAILED,
                started_at=instant(),
                ended_at=instant(),
                message="realtime health check failed",
                details={"ready_for_strategy": False, "global_mode": "paper", "high_priority_alerts": 1},
            ),
            AutomationTaskResult(
                task_name=AutomationTaskName.STRATEGY_BATCH,
                status=AutomationTaskStatus.SKIPPED,
                started_at=instant(),
                ended_at=instant(),
                message="strategy batch skipped",
                details={"successful_runs": 0, "failed_strategies": 0, "run_ids": []},
            ),
        ],
    )


def write_run_bundle(artifact_root: Path) -> None:
    manifest = report_manifest(
        run_id="run-yesterday",
        start_time=instant() - timedelta(days=1, hours=2),
        end_time=instant() - timedelta(days=1, hours=1),
    )
    RunArtifactBundleWriter(artifact_root).write_bundle(
        manifest,
        positions=[{"token_id": "token-yes", "quantity": "3", "mark_price": "0.52"}],
        risk_decisions=[
            {
                "token_id": "token-yes",
                "decision": "WARN",
                "warnings": ["spread_warning"],
                "created_at": manifest.end_time,
            }
        ],
        strategy_log="strategy log",
        framework_log="framework log",
    )


def test_report_context_uses_calendar_yesterday_window(tmp_path: Path) -> None:
    artifact_root = tmp_path / "runs"
    write_run_bundle(artifact_root)
    builder = ReportBuilder(OperatorQueryService(artifact_root))

    context = builder.build_report_context(automation_run(tmp_path), now=instant())

    assert context["window_start"] == datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc)
    assert context["window_end"].date().isoformat() == "2026-04-21"


def test_report_context_surfaces_failed_and_skipped_tasks(tmp_path: Path) -> None:
    artifact_root = tmp_path / "runs"
    write_run_bundle(artifact_root)
    builder = ReportBuilder(OperatorQueryService(artifact_root))

    context = builder.build_report_context(automation_run(tmp_path), now=instant())

    statuses = {row["task_name"]: row["status"] for row in context["task_results"]}
    assert statuses["realtime_health_check"] == "failed"
    assert statuses["strategy_batch"] == "skipped"


def test_markdown_report_contains_required_sections(tmp_path: Path) -> None:
    artifact_root = tmp_path / "runs"
    write_run_bundle(artifact_root)
    builder = ReportBuilder(OperatorQueryService(artifact_root))

    markdown_report = builder.render_markdown_report(
        builder.build_report_context(automation_run(tmp_path), now=instant())
    )

    assert "## Run Overview" in markdown_report
    assert "## Market Sync Summary" in markdown_report
    assert "## Realtime Health Summary" in markdown_report
    assert "## Strategy Run Summary" in markdown_report
    assert "## PnL / Drawdown / Exposure" in markdown_report
    assert "## Alerts Summary" in markdown_report
    assert "## Runs / Artifacts" in markdown_report


def test_markdown_report_marks_unhealthy_tasks(tmp_path: Path) -> None:
    artifact_root = tmp_path / "runs"
    write_run_bundle(artifact_root)
    builder = ReportBuilder(OperatorQueryService(artifact_root))

    markdown_report = builder.render_markdown_report(
        builder.build_report_context(automation_run(tmp_path), now=instant())
    )

    assert "## Unhealthy Tasks" in markdown_report
    assert "realtime_health_check: failed" in markdown_report


def test_markdown_report_lists_strategy_level_failures(tmp_path: Path) -> None:
    artifact_root = tmp_path / "runs"
    builder = ReportBuilder(OperatorQueryService(artifact_root))
    failed_run = automation_run(tmp_path).model_copy(
        update={
            "task_results": [
                task.model_copy(
                    update={
                        "status": AutomationTaskStatus.FAILED,
                        "message": "strategy batch failed",
                        "details": {
                            "successful_runs": 1,
                            "failed_strategies": 1,
                            "strategies": [
                                {
                                    "name": "bad_strategy",
                                    "status": "failed",
                                    "error": "intentional failure",
                                },
                                {
                                    "name": "good_strategy",
                                    "status": "success",
                                    "run_id": "good-run-001",
                                },
                            ],
                        },
                        "run_ids": ["good-run-001"],
                    }
                )
                if task.task_name == AutomationTaskName.STRATEGY_BATCH
                else task
                for task in automation_run(tmp_path).task_results
            ]
        }
    )

    markdown_report = builder.render_markdown_report(
        builder.build_report_context(failed_run, now=instant())
    )

    assert "### Strategy Details" in markdown_report
    assert "bad_strategy" in markdown_report
    assert "intentional failure" in markdown_report
    assert "good-run-001" in markdown_report


def test_report_context_falls_back_to_current_automation_runs_when_window_is_empty(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "runs"
    current_manifest = report_manifest(
        run_id="run-current",
        start_time=instant(),
        end_time=instant() + timedelta(minutes=5),
    )
    RunArtifactBundleWriter(artifact_root).write_bundle(
        current_manifest,
        positions=[{"token_id": "token-yes", "quantity": "2", "mark_price": "0.51"}],
        risk_decisions=[
            {
                "token_id": "token-yes",
                "decision": "WARN",
                "warnings": ["drawdown_warning"],
                "created_at": current_manifest.end_time,
            }
        ],
        strategy_log="strategy log",
        framework_log="framework log",
    )
    builder = ReportBuilder(OperatorQueryService(artifact_root))
    current_run = automation_run(tmp_path).model_copy(
        update={
            "task_results": [
                task.model_copy(update={"run_ids": ["run-current"]})
                if task.task_name == AutomationTaskName.STRATEGY_BATCH
                else task
                for task in automation_run(tmp_path).task_results
            ]
        }
    )

    context = builder.build_report_context(current_run, now=instant())

    assert context["pnl_exposure_source"] == "current_automation_runs"
    assert context["runs_artifacts_source"] == "current_automation_runs"
    assert context["alerts_source"] == "current_automation_runs"
    assert context["pnl_exposure"][0]["run_id"] == "run-current"
    assert context["runs_artifacts"][0]["run_id"] == "run-current"


def test_markdown_report_labels_fallback_sources(tmp_path: Path) -> None:
    artifact_root = tmp_path / "runs"
    current_manifest = report_manifest(
        run_id="run-current",
        start_time=instant(),
        end_time=instant() + timedelta(minutes=5),
    )
    RunArtifactBundleWriter(artifact_root).write_bundle(
        current_manifest,
        strategy_log="strategy log",
        framework_log="framework log",
    )
    builder = ReportBuilder(OperatorQueryService(artifact_root))
    current_run = automation_run(tmp_path).model_copy(
        update={
            "task_results": [
                task.model_copy(update={"run_ids": ["run-current"]})
                if task.task_name == AutomationTaskName.STRATEGY_BATCH
                else task
                for task in automation_run(tmp_path).task_results
            ]
        }
    )

    markdown_report = builder.render_markdown_report(
        builder.build_report_context(current_run, now=instant())
    )

    assert "_Source: current automation strategy runs_" in markdown_report
    assert "_No alerts recorded in the report window or this automation run._" in markdown_report or "run-current" in markdown_report
