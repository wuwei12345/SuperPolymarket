from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from polymarket_quant.domain.automation import AutomationTaskName
from polymarket_quant.domain.market_data import utc_now
from polymarket_quant.services.automation_cli import AutomationCliService
from polymarket_quant.services.automation_config import load_automation_config
from polymarket_quant.services.automation_runner import AutomationRunResult
from polymarket_quant.services.dashboard_snapshot import DashboardSnapshotService
from polymarket_quant.services.operator_queries import OperatorQueryService
from polymarket_quant.services.runtime_state_store import RuntimeStateStore, RuntimeTaskState


TASK_ORDER = [
    AutomationTaskName.MARKET_SYNC,
    AutomationTaskName.REALTIME_HEALTH_CHECK,
    AutomationTaskName.STRATEGY_BATCH,
    AutomationTaskName.REPORT_GENERATION,
]

TASK_ALIASES = {
    "market_sync": AutomationTaskName.MARKET_SYNC,
    "realtime_health_check": AutomationTaskName.REALTIME_HEALTH_CHECK,
    "health_check": AutomationTaskName.REALTIME_HEALTH_CHECK,
    "strategy_batch": AutomationTaskName.STRATEGY_BATCH,
    "daily_report": AutomationTaskName.REPORT_GENERATION,
    "report_generation": AutomationTaskName.REPORT_GENERATION,
}


class DaemonTaskSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_name: AutomationTaskName
    interval_seconds: int = Field(gt=0)
    enabled: bool = True


class DaemonResolvedConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    automation_config_path: str
    runtime_root: str = "data/runtime"
    poll_interval_seconds: int = Field(default=30, gt=0)
    tasks: list[DaemonTaskSchedule] = Field(default_factory=list)


class BackgroundDaemonService:
    def __init__(
        self,
        config: DaemonResolvedConfig,
        *,
        state_store: RuntimeStateStore | None = None,
        run_callable: Callable[[list[AutomationTaskName]], AutomationRunResult] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self.config = config
        runtime_root = Path(config.runtime_root)
        self.state_store = state_store or RuntimeStateStore(runtime_root / "daemon_state.json")
        self.run_callable = run_callable or self._run_automation_tasks
        self.sleep = sleep
        self.now = now

    @classmethod
    def from_file(
        cls,
        config_path: str | Path = "config/daemon.local.yaml",
        **kwargs: Any,
    ) -> "BackgroundDaemonService":
        return cls(load_daemon_config(config_path), **kwargs)

    def run_forever(self, *, max_cycles: int | None = None) -> None:
        with self.state_store.lock():
            self.state_store.clear_stop()
            cycles = 0
            while not self.state_store.should_stop():
                self.state_store.heartbeat(at=self.now())
                self.run_due_once()
                cycles += 1
                if max_cycles is not None and cycles >= max_cycles:
                    break
                self.sleep(self.config.poll_interval_seconds)
            state = self.state_store.load()
            self.state_store.save(state.model_copy(update={"status": "stopped", "current_task": None}))

    def run_due_once(self) -> list[AutomationTaskName]:
        current_time = self.now()
        due_tasks = self._due_tasks(current_time)
        if not due_tasks:
            self._refresh_next_run(current_time)
            return []

        task_label = "+".join(task.value for task in due_tasks)
        self.state_store.start_task(task_label, at=current_time)
        try:
            result = self.run_callable(due_tasks)
            next_time = self._next_time_for_tasks(due_tasks, current_time)
            self.state_store.finish_task(
                task_label,
                at=self.now(),
                next_run_at=next_time,
                recent_run_id=result.automation_run.run_id,
                recent_report_path=_report_path(result),
            )
            self._mark_individual_tasks(due_tasks, status="success", at=self.now())
            self._write_snapshot(result)
            return due_tasks
        except Exception as exc:
            next_time = self._next_time_for_tasks(due_tasks, current_time)
            self.state_store.fail_task(task_label, str(exc), at=self.now(), next_run_at=next_time)
            self._mark_individual_tasks(due_tasks, status="failed", error=str(exc), at=self.now())
            raise

    def request_stop(self) -> None:
        self.state_store.request_stop()

    def _run_automation_tasks(self, task_names: list[AutomationTaskName]) -> AutomationRunResult:
        resolved_config = load_automation_config(self.config.automation_config_path)
        resolved_config = resolved_config.model_copy(
            update={
                "enabled_tasks": task_names,
                "metadata": {**resolved_config.metadata, "runtime_root": self.config.runtime_root},
            }
        )
        return AutomationCliService().run_resolved(resolved_config)

    def _write_snapshot(self, result: AutomationRunResult) -> None:
        artifact_root = result.automation_run.resolved_config.artifact_root
        DashboardSnapshotService(
            OperatorQueryService(artifact_root),
            snapshot_path=Path(self.config.runtime_root) / "latest_snapshot.json",
        ).write_latest(automation_run=result.automation_run)

    def _due_tasks(self, current_time: datetime) -> list[AutomationTaskName]:
        state = self.state_store.load()
        due: list[AutomationTaskName] = []
        for schedule in self.config.tasks:
            if not schedule.enabled:
                continue
            task_state = state.tasks.get(schedule.task_name.value)
            if task_state is None or task_state.next_run_at is None or task_state.next_run_at <= current_time:
                due.append(schedule.task_name)
        due_set = set(due)
        return [task for task in TASK_ORDER if task in due_set]

    def _next_time_for_tasks(
        self,
        task_names: list[AutomationTaskName],
        current_time: datetime,
    ) -> datetime | None:
        next_times = []
        task_set = set(task_names)
        for schedule in self.config.tasks:
            if schedule.task_name in task_set:
                next_times.append(current_time + timedelta(seconds=schedule.interval_seconds))
        return min(next_times, default=None)

    def _refresh_next_run(self, current_time: datetime) -> None:
        state = self.state_store.load()
        next_run_at = min(
            (
                state.tasks.get(schedule.task_name.value).next_run_at
                for schedule in self.config.tasks
                if state.tasks.get(schedule.task_name.value) is not None
                and state.tasks[schedule.task_name.value].next_run_at is not None
            ),
            default=current_time,
        )
        self.state_store.save(state.model_copy(update={"next_run_at": next_run_at}))

    def _mark_individual_tasks(
        self,
        task_names: list[AutomationTaskName],
        *,
        status: str,
        at: datetime,
        error: str | None = None,
    ) -> None:
        state = self.state_store.load()
        tasks = dict(state.tasks)
        for task_name in task_names:
            schedule = next(
                schedule for schedule in self.config.tasks if schedule.task_name == task_name
            )
            existing = tasks.get(task_name.value)
            update = {
                "name": task_name.value,
                "last_started_at": state.last_started_at,
                "last_finished_at": at,
                "next_run_at": at + timedelta(seconds=schedule.interval_seconds),
                "last_status": status,
                "last_error": error,
            }
            tasks[task_name.value] = (
                existing.model_copy(update=update) if existing is not None else RuntimeTaskState(**update)
            )
        self.state_store.save(
            state.model_copy(
                update={
                    "tasks": tasks,
                    "next_run_at": min(
                        (
                            task.next_run_at
                            for task in tasks.values()
                            if task.next_run_at is not None
                            and task.name in {schedule.task_name.value for schedule in self.config.tasks}
                        ),
                        default=state.next_run_at,
                    ),
                }
            )
        )


def load_daemon_config(path: str | Path) -> DaemonResolvedConfig:
    config_path = Path(path)
    raw = yaml.safe_load(config_path.read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError("daemon config must deserialize into an object")
    base_dir = config_path.parent
    runtime_root = _resolve_path(Path.cwd(), raw.get("runtime_root", "data/runtime"))
    automation_config_path = _resolve_path(
        base_dir,
        raw.get("automation_config_path", "automation.daily.yaml"),
    )
    raw_tasks = raw.get("tasks") or {}
    if not isinstance(raw_tasks, dict):
        raise ValueError("daemon tasks must be an object")
    schedules = []
    for raw_name, raw_schedule in raw_tasks.items():
        if not isinstance(raw_schedule, dict):
            raise ValueError("each daemon task schedule must be an object")
        schedules.append(
            DaemonTaskSchedule(
                task_name=TASK_ALIASES[str(raw_name)],
                interval_seconds=int(raw_schedule.get("interval_seconds", 3600)),
                enabled=bool(raw_schedule.get("enabled", True)),
            )
        )
    return DaemonResolvedConfig(
        automation_config_path=str(automation_config_path),
        runtime_root=str(runtime_root),
        poll_interval_seconds=int(raw.get("poll_interval_seconds", 30)),
        tasks=schedules,
    )


def _resolve_path(base_path: Path, raw_path: Any) -> Path:
    path = Path(str(raw_path))
    if path.is_absolute():
        return path
    return (base_path / path).resolve()


def _report_path(result: AutomationRunResult) -> str | None:
    report = result.report
    if report is None:
        return None
    return report.html_path or report.markdown_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the lightweight simulation daemon.")
    parser.add_argument(
        "--config",
        default="config/daemon.local.yaml",
        help="Path to daemon YAML config",
    )
    parser.add_argument("--once", action="store_true", help="Run one due cycle and exit")
    parser.add_argument("--stop", action="store_true", help="Request daemon stop and exit")
    args = parser.parse_args(argv)

    service = BackgroundDaemonService.from_file(args.config)
    if args.stop:
        service.request_stop()
        print("stop_requested=true")
        return 0
    if args.once:
        with service.state_store.lock():
            tasks = service.run_due_once()
        print("due_tasks=" + ",".join(task.value for task in tasks))
        return 0
    service.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
