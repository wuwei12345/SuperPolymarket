from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polymarket_quant.domain.market_data import utc_now
from polymarket_quant.domain.strategy import RunMode


class AutomationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "run_id",
        "name",
        "strategy_class",
        "config_path",
        "environment",
        "artifact_root",
        "automation_root",
        "report_output_dir",
        "window_policy",
        "timezone",
        "message",
        check_fields=False,
    )
    @classmethod
    def non_blank_strings(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("string fields cannot be blank")
        return value


class AutomationTaskName(StrEnum):
    MARKET_SYNC = "market_sync"
    REALTIME_HEALTH_CHECK = "realtime_health_check"
    STRATEGY_BATCH = "strategy_batch"
    REPORT_GENERATION = "report_generation"


class AutomationTaskStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ReportFormat(StrEnum):
    MARKDOWN = "markdown"
    HTML = "html"


class AutomationStrategyDefinition(AutomationModel):
    name: str = Field(min_length=1)
    strategy_class: str = Field(min_length=1)
    config_path: str = Field(min_length=1)
    enabled: bool = True


class AutomationResolvedConfig(AutomationModel):
    environment: str = Field(min_length=1, default="local")
    mode: RunMode = RunMode.REALTIME_PAPER
    enabled_tasks: list[AutomationTaskName] = Field(default_factory=list)
    strategies: list[AutomationStrategyDefinition] = Field(default_factory=list)
    artifact_root: str = Field(min_length=1)
    automation_root: str = Field(min_length=1)
    report_output_dir: str = Field(min_length=1)
    market_store_path: str = Field(min_length=1)
    report_formats: list[ReportFormat] = Field(default_factory=list)
    window_policy: str = Field(min_length=1, default="calendar_yesterday")
    timezone: str = Field(min_length=1, default="UTC")
    raw_config_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AutomationTaskResult(AutomationModel):
    task_name: AutomationTaskName
    status: AutomationTaskStatus
    started_at: datetime
    ended_at: datetime
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)
    run_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ReportReference(AutomationModel):
    window_start: datetime
    window_end: datetime
    markdown_path: str = Field(min_length=1)
    html_path: str | None = None
    index_path: str | None = None


class AutomationRun(AutomationModel):
    run_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    mode: RunMode
    started_at: datetime
    ended_at: datetime | None = None
    resolved_config: AutomationResolvedConfig
    task_results: list[AutomationTaskResult] = Field(default_factory=list)
    report: ReportReference | None = None
    framework_log: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
