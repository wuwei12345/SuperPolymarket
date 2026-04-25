from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from polymarket_quant.domain.automation import AutomationRun, AutomationTaskName
from polymarket_quant.services.operator_queries import OperatorFilters, OperatorQueryService
from polymarket_quant.services.report_templates import (
    ALERTS_TITLE,
    MARKET_SYNC_TITLE,
    PNL_EXPOSURE_TITLE,
    REALTIME_HEALTH_TITLE,
    RUN_OVERVIEW_TITLE,
    RUNS_ARTIFACTS_TITLE,
    STRATEGY_SUMMARY_TITLE,
    isoformat,
    render_key_values,
    render_table,
    render_task_status_lines,
)


class ReportBuilder:
    def __init__(self, query_service: OperatorQueryService) -> None:
        self.query_service = query_service

    def build_report_context(
        self,
        automation_run: AutomationRun,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        window_start, window_end = calendar_yesterday_window(
            now=now,
            timezone_name=automation_run.resolved_config.timezone,
        )
        filters = OperatorFilters(window_start=window_start, window_end=window_end)
        task_results = [task.model_dump(mode="json") for task in automation_run.task_results]
        strategy_run_ids = _strategy_run_ids(automation_run)
        window_pnl_exposure = self.query_service.pnl_exposure(filters)
        window_alerts = self.query_service.alerts_timeline(filters)
        window_runs_artifacts = self.query_service.runs_artifacts(filters)
        current_pnl_exposure = self.query_service.pnl_exposure_for_run_ids(strategy_run_ids)
        current_alerts = self.query_service.alerts_timeline_for_run_ids(strategy_run_ids)
        current_runs_artifacts = self.query_service.runs_artifacts_for_run_ids(strategy_run_ids)
        return {
            "run_id": automation_run.run_id,
            "environment": automation_run.environment,
            "mode": automation_run.mode.value,
            "window_label": "yesterday",
            "window_start": window_start,
            "window_end": window_end,
            "task_results": task_results,
            "market_sync": _task_details(automation_run, AutomationTaskName.MARKET_SYNC),
            "realtime_health": _task_details(
                automation_run, AutomationTaskName.REALTIME_HEALTH_CHECK
            ),
            "strategy_batch": _task_details(automation_run, AutomationTaskName.STRATEGY_BATCH),
            "strategy_results": _task_details(
                automation_run, AutomationTaskName.STRATEGY_BATCH
            ).get("strategies", []),
            "status_band": self.query_service.status_band(filters),
            "overview": self.query_service.overview(group_by="strategy", filters=filters),
            "pnl_exposure": window_pnl_exposure or current_pnl_exposure,
            "alerts": window_alerts or current_alerts,
            "runs_artifacts": window_runs_artifacts or current_runs_artifacts,
            "pnl_exposure_source": _section_source(
                window_pnl_exposure,
                current_pnl_exposure,
                "report_window",
                "current_automation_runs",
            ),
            "alerts_source": _section_source(
                window_alerts,
                current_alerts,
                "report_window",
                "current_automation_runs",
            ),
            "runs_artifacts_source": _section_source(
                window_runs_artifacts,
                current_runs_artifacts,
                "report_window",
                "current_automation_runs",
            ),
            "unhealthy_tasks": [
                task.model_dump(mode="json")
                for task in automation_run.task_results
                if task.status.value != "success"
            ],
        }

    def render_markdown_report(self, context: dict[str, Any]) -> str:
        overview = context["overview"]
        pnl_exposure = context["pnl_exposure"]
        alerts = context["alerts"]
        runs_artifacts = context["runs_artifacts"]
        status_band = context["status_band"]
        pnl_source = _source_label(context["pnl_exposure_source"])
        alerts_source = _source_label(context["alerts_source"])
        runs_source = _source_label(context["runs_artifacts_source"])
        lines = [
            "# Daily Automation Report",
            "",
            f"## {RUN_OVERVIEW_TITLE}",
            render_key_values(
                [
                    ("Automation run", context["run_id"]),
                    ("Environment", context["environment"]),
                    ("Mode", context["mode"]),
                    (
                        "Yesterday window",
                        f"{isoformat(context['window_start'])} -> {isoformat(context['window_end'])}",
                    ),
                    ("Global mode", getattr(status_band.get("global_mode"), "value", "n/a")),
                    ("High priority alerts", status_band.get("high_priority_alerts", 0)),
                ]
            ),
            "",
            "### Task Status",
            render_task_status_lines(context["task_results"]),
            "",
            f"## {MARKET_SYNC_TITLE}",
            render_key_values(
                [
                    ("Status", context["market_sync"].get("status", "missing")),
                    ("Written markets", context["market_sync"].get("written_count", 0)),
                    ("Skipped markets", context["market_sync"].get("skipped_count", 0)),
                    ("Errors", ", ".join(context["market_sync"].get("errors", [])) or "none"),
                ]
            ),
            "",
            f"## {REALTIME_HEALTH_TITLE}",
            render_key_values(
                [
                    ("Status", context["realtime_health"].get("status", "missing")),
                    (
                        "Ready for strategy",
                        context["realtime_health"].get("ready_for_strategy", False),
                    ),
                    ("Global mode", context["realtime_health"].get("global_mode", "n/a")),
                    (
                        "High priority alerts",
                        context["realtime_health"].get("high_priority_alerts", 0),
                    ),
                ]
            ),
            "",
            f"## {STRATEGY_SUMMARY_TITLE}",
            render_key_values(
                [
                    ("Status", context["strategy_batch"].get("status", "missing")),
                    ("Successful runs", context["strategy_batch"].get("successful_runs", 0)),
                    ("Failed strategies", context["strategy_batch"].get("failed_strategies", 0)),
                    (
                        "Run IDs",
                        ", ".join(context["strategy_batch"].get("run_ids", [])) or "none",
                    ),
                ]
            ),
            "",
            "### Strategy Details",
            render_table(
                ["strategy", "status", "run_id", "error"],
                [
                    [
                        row.get("name"),
                        row.get("status"),
                        row.get("run_id") or "-",
                        row.get("error") or "-",
                    ]
                    for row in context["strategy_results"]
                ],
                empty_message="_No strategies were executed._",
            ),
            "",
            f"## {PNL_EXPOSURE_TITLE}",
            f"_Source: {pnl_source}_",
            render_table(
                ["strategy", "realized_pnl", "unrealized_pnl", "turnover", "max_drawdown", "exposure_peak"],
                [
                    [
                        row.get("strategy"),
                        row.get("realized_pnl", Decimal("0")),
                        row.get("unrealized_pnl", Decimal("0")),
                        row.get("turnover", Decimal("0")),
                        row.get("max_drawdown", Decimal("0")),
                        row.get("exposure_peak", Decimal("0")),
                    ]
                    for row in pnl_exposure
                ],
                empty_message="_No strategy metrics found in the report window or this automation run._",
            ),
            "",
            f"## {ALERTS_TITLE}",
            f"_Source: {alerts_source}_",
            render_table(
                ["severity", "strategy", "message", "ts"],
                [
                    [
                        row.get("severity"),
                        row.get("strategy") or "-",
                        row.get("message"),
                        row.get("ts"),
                    ]
                    for row in alerts[:10]
                ],
                empty_message="_No alerts recorded in the report window or this automation run._",
            ),
            "",
            f"## {RUNS_ARTIFACTS_TITLE}",
            f"_Source: {runs_source}_",
            render_table(
                ["strategy", "run_id", "mode", "run_directory"],
                [
                    [
                        row.get("strategy_name"),
                        row.get("run_id"),
                        row.get("mode"),
                        row.get("run_directory"),
                    ]
                    for row in runs_artifacts[:10]
                ],
                empty_message="_No strategy artifacts found in the report window or this automation run._",
            ),
        ]
        if context["unhealthy_tasks"]:
            lines.extend(
                [
                    "",
                    "## Unhealthy Tasks",
                    render_task_status_lines(context["unhealthy_tasks"]),
                ]
            )
        return "\n".join(lines).strip() + "\n"


def calendar_yesterday_window(
    *,
    now: datetime | None = None,
    timezone_name: str = "UTC",
) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone_name)
    current = now.astimezone(zone) if now is not None else datetime.now(zone)
    yesterday = current.date() - timedelta(days=1)
    window_start = datetime.combine(yesterday, time.min, tzinfo=zone)
    window_end = datetime.combine(yesterday, time.max, tzinfo=zone)
    return window_start, window_end


def build_report_context(
    automation_run: AutomationRun,
    query_service: OperatorQueryService,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    return ReportBuilder(query_service).build_report_context(automation_run, now=now)


def render_markdown_report(context: dict[str, Any]) -> str:
    class _ContextOnlyQueryService:
        def __init__(self) -> None:
            raise RuntimeError("use ReportBuilder for rendering with a live query service")

    del _ContextOnlyQueryService
    builder = object.__new__(ReportBuilder)
    return ReportBuilder.render_markdown_report(builder, context)


def _task_details(automation_run: AutomationRun, task_name: AutomationTaskName) -> dict[str, Any]:
    for task_result in automation_run.task_results:
        if task_result.task_name == task_name:
            return {
                "status": task_result.status.value,
                "message": task_result.message,
                "run_ids": list(task_result.run_ids),
                **task_result.details,
            }
    return {}


def _strategy_run_ids(automation_run: AutomationRun) -> list[str]:
    task_details = _task_details(automation_run, AutomationTaskName.STRATEGY_BATCH)
    run_ids = task_details.get("run_ids", [])
    if run_ids:
        return list(run_ids)
    return [
        run_id
        for task_result in automation_run.task_results
        if task_result.task_name == AutomationTaskName.STRATEGY_BATCH
        for run_id in task_result.run_ids
    ]


def _section_source(
    window_rows: list[dict[str, Any]],
    current_rows: list[dict[str, Any]],
    window_label: str,
    current_label: str,
) -> str:
    if window_rows:
        return window_label
    if current_rows:
        return current_label
    return "none"


def _source_label(source: str) -> str:
    if source == "report_window":
        return "yesterday window"
    if source == "current_automation_runs":
        return "current automation strategy runs"
    return "no matching records"
