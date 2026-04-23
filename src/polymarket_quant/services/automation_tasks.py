from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from importlib import import_module
from typing import Any

from polymarket_quant.domain.automation import (
    AutomationResolvedConfig,
    AutomationStrategyDefinition,
    AutomationTaskName,
    AutomationTaskResult,
    AutomationTaskStatus,
)
from polymarket_quant.domain.market_data import utc_now
from polymarket_quant.domain.operator import ConnectionStatus, GlobalMode


def run_market_sync(
    sync_callable: Callable[[], Any],
    *,
    now: Callable[[], datetime] = utc_now,
) -> AutomationTaskResult:
    started_at = now()
    try:
        result = sync_callable()
        details = _market_sync_details(result)
        status = (
            AutomationTaskStatus.SUCCESS
            if not details["errors"] or details["written_count"] > 0
            else AutomationTaskStatus.FAILED
        )
        return AutomationTaskResult(
            task_name=AutomationTaskName.MARKET_SYNC,
            status=status,
            started_at=started_at,
            ended_at=now(),
            message="market sync completed" if status == AutomationTaskStatus.SUCCESS else "market sync failed",
            details=details,
            errors=list(details["errors"]),
        )
    except Exception as exc:
        return AutomationTaskResult(
            task_name=AutomationTaskName.MARKET_SYNC,
            status=AutomationTaskStatus.FAILED,
            started_at=started_at,
            ended_at=now(),
            message="market sync failed",
            errors=[str(exc)],
        )


def run_realtime_health_check(
    *,
    health_callable: Callable[[], dict[str, Any]] | None = None,
    now: Callable[[], datetime] = utc_now,
) -> AutomationTaskResult:
    started_at = now()
    try:
        details = dict((health_callable or _default_health_check)())
        status = (
            AutomationTaskStatus.SUCCESS
            if details.get("ready_for_strategy", False)
            else AutomationTaskStatus.FAILED
        )
        message = (
            "realtime health check passed"
            if status == AutomationTaskStatus.SUCCESS
            else "realtime health check failed"
        )
        return AutomationTaskResult(
            task_name=AutomationTaskName.REALTIME_HEALTH_CHECK,
            status=status,
            started_at=started_at,
            ended_at=now(),
            message=message,
            details=details,
            errors=[] if status == AutomationTaskStatus.SUCCESS else [message],
        )
    except Exception as exc:
        return AutomationTaskResult(
            task_name=AutomationTaskName.REALTIME_HEALTH_CHECK,
            status=AutomationTaskStatus.FAILED,
            started_at=started_at,
            ended_at=now(),
            message="realtime health check failed",
            errors=[str(exc)],
        )


def run_strategy_batch(
    resolved_config: AutomationResolvedConfig,
    *,
    strategy_executor: Callable[[AutomationStrategyDefinition], Any],
    now: Callable[[], datetime] = utc_now,
) -> AutomationTaskResult:
    started_at = now()
    strategies = [strategy for strategy in resolved_config.strategies if strategy.enabled]
    if not strategies:
        return AutomationTaskResult(
            task_name=AutomationTaskName.STRATEGY_BATCH,
            status=AutomationTaskStatus.SKIPPED,
            started_at=started_at,
            ended_at=now(),
            message="strategy batch skipped",
            details={"reason": "no enabled strategies"},
        )

    run_ids: list[str] = []
    strategy_results: list[dict[str, Any]] = []
    errors: list[str] = []
    for strategy in strategies:
        try:
            execution_result = strategy_executor(strategy)
            run_id = _extract_run_id(execution_result)
            if run_id is not None:
                run_ids.append(run_id)
            strategy_results.append(
                {
                    "name": strategy.name,
                    "status": "success",
                    "run_id": run_id,
                }
            )
        except Exception as exc:
            errors.append(f"{strategy.name}: {exc}")
            strategy_results.append(
                {
                    "name": strategy.name,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    status = AutomationTaskStatus.SUCCESS if not errors else AutomationTaskStatus.FAILED
    return AutomationTaskResult(
        task_name=AutomationTaskName.STRATEGY_BATCH,
        status=status,
        started_at=started_at,
        ended_at=now(),
        message="strategy batch completed" if status == AutomationTaskStatus.SUCCESS else "strategy batch failed",
        details={
            "strategies": strategy_results,
            "strategy_count": len(strategies),
            "successful_runs": len(run_ids),
            "failed_strategies": len(errors),
        },
        run_ids=run_ids,
        errors=errors,
    )


def load_object(path: str) -> Any:
    module_name, _, attribute = path.partition(":")
    if not module_name or not attribute:
        raise ValueError("strategy_class must use 'module:attribute' format")
    module = import_module(module_name)
    return getattr(module, attribute)


def _extract_run_id(execution_result: Any) -> str | None:
    manifest = getattr(execution_result, "manifest", None)
    if manifest is not None:
        return getattr(manifest, "run_id", None)
    if isinstance(execution_result, dict):
        return execution_result.get("run_id")
    return getattr(execution_result, "run_id", None)


def _market_sync_details(result: Any) -> dict[str, Any]:
    return {
        "written_count": int(getattr(result, "written_count", 0)),
        "skipped_count": int(getattr(result, "skipped_count", 0)),
        "errors": list(getattr(result, "errors", [])),
        "event_count": len(getattr(result, "events", [])),
    }


def _default_health_check() -> dict[str, Any]:
    return {
        "global_mode": GlobalMode.PAPER.value,
        "connections": [],
        "high_priority_alerts": 0,
        "ready_for_strategy": True,
    }


def health_details_from_status_band(status_band: dict[str, Any]) -> dict[str, Any]:
    connections = status_band.get("connections", [])
    has_down_connection = any(
        getattr(connection, "status", None) == ConnectionStatus.DOWN for connection in connections
    )
    global_mode = status_band.get("global_mode")
    return {
        "global_mode": getattr(global_mode, "value", global_mode),
        "connections": [
            {
                "component": getattr(connection.component, "value", str(connection.component)),
                "status": getattr(connection.status, "value", str(connection.status)),
                "detail": getattr(connection, "detail", None),
            }
            for connection in connections
        ],
        "high_priority_alerts": int(status_band.get("high_priority_alerts", 0)),
        "last_updated": (
            status_band.get("last_updated").isoformat()
            if status_band.get("last_updated") is not None
            else None
        ),
        "ready_for_strategy": not has_down_connection
        and getattr(global_mode, "value", global_mode) != GlobalMode.LIVE_DISABLED.value,
    }
