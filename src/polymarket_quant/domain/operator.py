from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polymarket_quant.domain.market_data import utc_now


class OperatorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator(
        "run_id",
        "strategy_name",
        "message",
        "detail",
        check_fields=False,
    )
    @classmethod
    def non_blank_strings(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("string fields cannot be blank")
        return value


class GlobalMode(StrEnum):
    REPLAY = "replay"
    PAPER = "paper"
    LIVE_DISABLED = "live-disabled"


class LocalRunMode(StrEnum):
    REPLAY = "replay"
    RESEARCH = "research"
    REALTIME_PAPER = "realtime_paper"


class ConnectionComponent(StrEnum):
    DB = "DB"
    MARKET_DATA_WS = "MARKET_DATA_WS"
    EXECUTION = "EXECUTION"
    RISK = "RISK"


class ConnectionStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class StrategyRuntimeState(StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    BLOCKED = "blocked"
    FINISHED = "finished"


class AlertSeverity(StrEnum):
    INFO = "Info"
    WARNING = "Warning"
    CRITICAL = "Critical"


class NewOrderBlockState(StrEnum):
    ALLOWED = "allowed"
    PARTIALLY_BLOCKED = "partially blocked"
    FULLY_BLOCKED = "fully blocked"


class ConnectionState(OperatorModel):
    component: ConnectionComponent
    status: ConnectionStatus
    detail: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class AlertSummary(OperatorModel):
    Info: int = 0
    Warning: int = 0
    Critical: int = 0


class RuntimeHeartbeat(OperatorModel):
    run_id: str = Field(min_length=1)
    last_heartbeat: datetime = Field(default_factory=utc_now)
    message: str | None = None


class RuntimeStatusSnapshot(OperatorModel):
    run_id: str = Field(min_length=1)
    strategy_name: str = Field(min_length=1)
    strategy_version: str = "dev"
    global_mode: GlobalMode
    local_mode: LocalRunMode
    state: StrategyRuntimeState
    new_order_status: NewOrderBlockState = NewOrderBlockState.ALLOWED
    alert_summary: AlertSummary = Field(default_factory=AlertSummary)
    last_heartbeat: datetime = Field(default_factory=utc_now)
    active_positions: int = 0
    open_orders: int = 0
    latest_pnl: float = 0.0
    latest_drawdown: float = 0.0
    error_message: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)

