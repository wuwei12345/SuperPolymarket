from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

from polymarket_quant.domain.automation import (
    AutomationResolvedConfig,
    AutomationRun,
    AutomationTaskName,
    AutomationTaskResult,
    AutomationTaskStatus,
    ReportReference,
)
from polymarket_quant.domain.market_data import utc_now
from polymarket_quant.services.automation_tasks import (
    health_details_from_status_band,
    run_market_sync,
    run_realtime_health_check,
    run_strategy_batch,
)
from polymarket_quant.services.operator_queries import OperatorQueryService
from polymarket_quant.services.report_builder import ReportBuilder
from polymarket_quant.services.report_outputs import write_report_outputs


class AutomationRunResult:
    def __init__(
        self,
        automation_run: AutomationRun,
        run_directory: Path,
    ) -> None:
        self.automation_run = automation_run
        self.run_directory = run_directory
        self.report = automation_run.report


class AutomationRunner:
    def __init__(
        self,
        *,
        sync_callable: Callable[[], Any] | None = None,
        health_callable: Callable[[], dict[str, Any]] | None = None,
        strategy_executor: Callable[[Any], Any] | None = None,
        query_service_factory: Callable[[AutomationResolvedConfig], OperatorQueryService]
        | None = None,
        report_output_writer: Callable[..., ReportReference] = write_report_outputs,
    ) -> None:
        self.sync_callable = sync_callable or (lambda: {"written_count": 0, "skipped_count": 0, "errors": []})
        self.health_callable = health_callable
        self.strategy_executor = strategy_executor or (lambda strategy: {"run_id": strategy.name})
        self.query_service_factory = query_service_factory or (
            lambda config: OperatorQueryService(config.artifact_root)
        )
        self.report_output_writer = report_output_writer

    def run(self, resolved_config: AutomationResolvedConfig) -> AutomationRunResult:
        started_at = utc_now()
        automation_run = AutomationRun(
            run_id=f"automation-{uuid4().hex[:12]}",
            environment=resolved_config.environment,
            mode=resolved_config.mode,
            started_at=started_at,
            resolved_config=resolved_config,
            framework_log=[],
        )

        query_service = self.query_service_factory(resolved_config)
        report_builder = ReportBuilder(query_service)
        sync_result: AutomationTaskResult | None = None
        health_result: AutomationTaskResult | None = None

        for task_name in resolved_config.enabled_tasks:
            if task_name == AutomationTaskName.MARKET_SYNC:
                sync_result = run_market_sync(self.sync_callable)
                automation_run.task_results.append(sync_result)
                self._log(automation_run, sync_result)
                continue

            if task_name == AutomationTaskName.REALTIME_HEALTH_CHECK:
                if self.health_callable is None:
                    health_result = run_realtime_health_check(
                        health_callable=lambda: health_details_from_status_band(
                            query_service.status_band()
                        )
                    )
                else:
                    health_result = run_realtime_health_check(health_callable=self.health_callable)
                automation_run.task_results.append(health_result)
                self._log(automation_run, health_result)
                continue

            if task_name == AutomationTaskName.STRATEGY_BATCH:
                if not self._strategy_prerequisites_ok(sync_result, health_result):
                    skipped_result = self._skipped_strategy_batch()
                    automation_run.task_results.append(skipped_result)
                    self._log(automation_run, skipped_result)
                    continue
                strategy_result = run_strategy_batch(
                    resolved_config,
                    strategy_executor=self.strategy_executor,
                )
                automation_run.task_results.append(strategy_result)
                self._log(automation_run, strategy_result)
                continue

            if task_name == AutomationTaskName.REPORT_GENERATION:
                report_result, report_reference = self._run_report_generation(
                    automation_run,
                    query_service=query_service,
                    report_builder=report_builder,
                )
                automation_run.task_results.append(report_result)
                automation_run.report = report_reference
                self._log(automation_run, report_result)

        automation_run = automation_run.model_copy(update={"ended_at": utc_now()})
        run_directory = self._write_run_bundle(automation_run)
        return AutomationRunResult(automation_run=automation_run, run_directory=run_directory)

    def _run_report_generation(
        self,
        automation_run: AutomationRun,
        *,
        query_service: OperatorQueryService,
        report_builder: ReportBuilder,
    ) -> tuple[AutomationTaskResult, ReportReference]:
        started_at = utc_now()
        context = report_builder.build_report_context(automation_run)
        markdown_report = report_builder.render_markdown_report(context)
        report_reference = self.report_output_writer(
            automation_run.resolved_config.report_output_dir,
            automation_run,
            markdown_report,
            report_formats=automation_run.resolved_config.report_formats,
            window_start=context["window_start"],
            window_end=context["window_end"],
        )
        task_result = AutomationTaskResult(
            task_name=AutomationTaskName.REPORT_GENERATION,
            status=AutomationTaskStatus.SUCCESS,
            started_at=started_at,
            ended_at=utc_now(),
            message="report generation completed",
            details={
                "markdown_path": report_reference.markdown_path,
                "html_path": report_reference.html_path,
                "index_path": report_reference.index_path,
            },
        )
        return task_result, report_reference

    def _strategy_prerequisites_ok(
        self,
        sync_result: AutomationTaskResult | None,
        health_result: AutomationTaskResult | None,
    ) -> bool:
        if sync_result is not None and sync_result.status == AutomationTaskStatus.FAILED:
            return False
        if health_result is not None and health_result.status == AutomationTaskStatus.FAILED:
            return False
        return True

    def _skipped_strategy_batch(self) -> AutomationTaskResult:
        started_at = utc_now()
        return AutomationTaskResult(
            task_name=AutomationTaskName.STRATEGY_BATCH,
            status=AutomationTaskStatus.SKIPPED,
            started_at=started_at,
            ended_at=utc_now(),
            message="strategy batch skipped",
            details={"reason": "prerequisites failed"},
        )

    def _write_run_bundle(self, automation_run: AutomationRun) -> Path:
        run_directory = Path(automation_run.resolved_config.automation_root) / automation_run.run_id
        run_directory.mkdir(parents=True, exist_ok=True)
        (run_directory / "manifest.json").write_text(
            json.dumps(automation_run.model_dump(mode="json"), indent=2, sort_keys=True)
        )
        (run_directory / "framework.log").write_text("\n".join(automation_run.framework_log) + "\n")
        return run_directory

    @staticmethod
    def _log(automation_run: AutomationRun, task_result: AutomationTaskResult) -> None:
        automation_run.framework_log.append(
            f"{task_result.task_name.value}:{task_result.status.value}:{task_result.message}"
        )
