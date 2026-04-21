from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polymarket_quant.domain.market_data import utc_now


class StrategyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "run_id",
        "strategy_name",
        "strategy_version",
        "token_id",
        "dataset_id",
        check_fields=False,
    )
    @classmethod
    def required_string_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("identifier cannot be blank")
        return value

    @field_validator("environment", check_fields=False)
    @classmethod
    def environment_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("environment cannot be blank")
        return value


class RunMode(StrEnum):
    REPLAY = "replay"
    REALTIME_PAPER = "realtime_paper"
    RESEARCH = "research"


class StrategyEventType(StrEnum):
    MARKET = "MARKET"
    EXECUTION = "EXECUTION"
    RISK = "RISK"
    SYSTEM = "SYSTEM"


class StrategySignal(StrategyModel):
    token_id: str = Field(min_length=1)
    target_exposure: Decimal | None = None
    target_position: Decimal | None = None
    ts: datetime
    reason_code: str | None = None
    confidence: Decimal | None = None

    @field_validator("reason_code")
    @classmethod
    def optional_reason_code_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("reason_code cannot be blank")
        return value

    @field_validator("confidence")
    @classmethod
    def confidence_is_probability(cls, value: Decimal | None) -> Decimal | None:
        if value is not None and (value < 0 or value > 1):
            raise ValueError("confidence must be between 0 and 1")
        return value

    @model_validator(mode="after")
    def requires_one_target(self) -> "StrategySignal":
        if self.target_exposure is None and self.target_position is None:
            raise ValueError("signal requires target_exposure or target_position")
        return self


class StrategyEvent(StrategyModel):
    event_type: StrategyEventType
    ts: datetime
    token_id: str | None = None
    condition_id: str | None = None
    source: str
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source")
    @classmethod
    def source_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source cannot be blank")
        return value

    @field_validator("condition_id", check_fields=False)
    @classmethod
    def optional_condition_id_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("condition_id cannot be blank")
        return value


class UniverseSnapshot(StrategyModel):
    dataset_id: str = Field(min_length=1)
    selection: dict[str, Any] = Field(default_factory=dict)
    token_ids: list[str] = Field(default_factory=list)
    token_mappings: list[dict[str, Any]] = Field(default_factory=list)
    window_start: datetime | None = None
    window_end: datetime | None = None
    includes_gap_fill: bool = False

    @field_validator("token_ids")
    @classmethod
    def token_ids_are_not_blank(cls, value: list[str]) -> list[str]:
        if any(not token_id.strip() for token_id in value):
            raise ValueError("token_ids cannot contain blanks")
        return value


class ResolvedRunConfig(StrategyModel):
    strategy: dict[str, Any] = Field(default_factory=dict)
    universe: dict[str, Any] = Field(default_factory=dict)
    sizing: dict[str, Any] = Field(default_factory=dict)
    execution: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    data_sources: dict[str, Any] = Field(default_factory=dict)
    mode: RunMode
    replay: dict[str, Any] = Field(default_factory=dict)
    realtime: dict[str, Any] = Field(default_factory=dict)
    step_interval: str | None = None


class StrategyContextSnapshot(StrategyModel):
    timestamp: datetime = Field(default_factory=utc_now)
    run_mode: RunMode
    market_data: dict[str, Any] = Field(default_factory=dict)
    features: dict[str, Any] = Field(default_factory=dict)
    portfolio: dict[str, Any] = Field(default_factory=dict)
    recent_fills: list[dict[str, Any]] = Field(default_factory=list)
    recent_risk_decisions: list[dict[str, Any]] = Field(default_factory=list)
    run_config: ResolvedRunConfig
    time_window: dict[str, Any] = Field(default_factory=dict)


class RunManifest(StrategyModel):
    run_id: str = Field(min_length=1)
    strategy_name: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    git_commit: str
    start_time: datetime
    end_time: datetime | None = None
    mode: RunMode
    environment: str = Field(min_length=1)
    resolved_config: ResolvedRunConfig
    universe_snapshot: UniverseSnapshot
    artifact_files: dict[str, str] = Field(default_factory=dict)
    metrics_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

