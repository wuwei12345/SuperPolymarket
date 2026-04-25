from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from polymarket_quant.domain.market_data import utc_now


class RuntimeTaskState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    next_run_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None


class RuntimeDaemonState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    daemon_id: str = Field(default_factory=lambda: f"daemon-{uuid4().hex[:12]}")
    status: str = "stopped"
    heartbeat_at: datetime | None = None
    current_task: str | None = None
    last_started_at: datetime | None = None
    last_finished_at: datetime | None = None
    next_run_at: datetime | None = None
    recent_error: str | None = None
    recent_run_id: str | None = None
    recent_report_path: str | None = None
    stop_requested: bool = False
    tasks: dict[str, RuntimeTaskState] = Field(default_factory=dict)


class RuntimeStateStore:
    def __init__(
        self,
        state_path: str | Path = "data/runtime/daemon_state.json",
        *,
        lock_path: str | Path | None = None,
        stop_flag_path: str | Path | None = None,
    ) -> None:
        self.state_path = Path(state_path)
        self.lock_path = Path(lock_path) if lock_path is not None else self.state_path.with_suffix(".lock")
        self.stop_flag_path = (
            Path(stop_flag_path)
            if stop_flag_path is not None
            else self.state_path.with_name("stop.flag")
        )

    def load(self) -> RuntimeDaemonState:
        if not self.state_path.exists():
            return RuntimeDaemonState()
        return RuntimeDaemonState.model_validate(json.loads(self.state_path.read_text()))

    def save(self, state: RuntimeDaemonState) -> RuntimeDaemonState:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp")
        temp_path.write_text(json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True))
        temp_path.replace(self.state_path)
        return state

    def heartbeat(self, *, at: datetime | None = None, status: str = "running") -> RuntimeDaemonState:
        state = self.load()
        return self.save(state.model_copy(update={"heartbeat_at": at or utc_now(), "status": status}))

    def start_task(self, task_name: str, *, at: datetime | None = None) -> RuntimeDaemonState:
        timestamp = at or utc_now()
        state = self.load()
        task_state = state.tasks.get(task_name, RuntimeTaskState(name=task_name))
        task_state = task_state.model_copy(update={"last_started_at": timestamp, "last_status": "running"})
        tasks = {**state.tasks, task_name: task_state}
        return self.save(
            state.model_copy(
                update={
                    "status": "running",
                    "heartbeat_at": timestamp,
                    "current_task": task_name,
                    "last_started_at": timestamp,
                    "recent_error": None,
                    "tasks": tasks,
                }
            )
        )

    def finish_task(
        self,
        task_name: str,
        *,
        at: datetime | None = None,
        next_run_at: datetime | None = None,
        recent_run_id: str | None = None,
        recent_report_path: str | None = None,
    ) -> RuntimeDaemonState:
        timestamp = at or utc_now()
        state = self.load()
        task_state = state.tasks.get(task_name, RuntimeTaskState(name=task_name))
        task_state = task_state.model_copy(
            update={
                "last_finished_at": timestamp,
                "next_run_at": next_run_at,
                "last_status": "success",
                "last_error": None,
            }
        )
        tasks = {**state.tasks, task_name: task_state}
        return self.save(
            state.model_copy(
                update={
                    "status": "running",
                    "heartbeat_at": timestamp,
                    "current_task": None,
                    "last_finished_at": timestamp,
                    "next_run_at": _earliest_next_run(tasks),
                    "recent_error": None,
                    "recent_run_id": recent_run_id or state.recent_run_id,
                    "recent_report_path": recent_report_path or state.recent_report_path,
                    "tasks": tasks,
                }
            )
        )

    def fail_task(
        self,
        task_name: str,
        error: str,
        *,
        at: datetime | None = None,
        next_run_at: datetime | None = None,
    ) -> RuntimeDaemonState:
        timestamp = at or utc_now()
        state = self.load()
        task_state = state.tasks.get(task_name, RuntimeTaskState(name=task_name))
        task_state = task_state.model_copy(
            update={
                "last_finished_at": timestamp,
                "next_run_at": next_run_at,
                "last_status": "failed",
                "last_error": error,
            }
        )
        tasks = {**state.tasks, task_name: task_state}
        return self.save(
            state.model_copy(
                update={
                    "status": "error",
                    "heartbeat_at": timestamp,
                    "current_task": None,
                    "last_finished_at": timestamp,
                    "next_run_at": _earliest_next_run(tasks),
                    "recent_error": error,
                    "tasks": tasks,
                }
            )
        )

    def request_stop(self) -> RuntimeDaemonState:
        self.stop_flag_path.parent.mkdir(parents=True, exist_ok=True)
        self.stop_flag_path.write_text("stop\n")
        state = self.load()
        return self.save(state.model_copy(update={"stop_requested": True}))

    def clear_stop(self) -> RuntimeDaemonState:
        if self.stop_flag_path.exists():
            self.stop_flag_path.unlink()
        state = self.load()
        return self.save(state.model_copy(update={"stop_requested": False}))

    def should_stop(self) -> bool:
        return self.stop_flag_path.exists() or self.load().stop_requested

    @contextmanager
    def lock(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd: int | None = None
        try:
            fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()}\n".encode())
            yield
        finally:
            if fd is not None:
                os.close(fd)
                if self.lock_path.exists():
                    self.lock_path.unlink()


def _earliest_next_run(tasks: dict[str, RuntimeTaskState]) -> datetime | None:
    return min(
        (task.next_run_at for task in tasks.values() if task.next_run_at is not None),
        default=None,
    )
