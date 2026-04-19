from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polymarket_quant.domain.market_data import utc_now


class SimulationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("client_order_id", "strategy_id", "token_id", check_fields=False)
    @classmethod
    def required_id_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("identifier cannot be blank")
        return value

    @field_validator("condition_id", check_fields=False)
    @classmethod
    def optional_condition_id_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("condition_id cannot be blank")
        return value


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    LIMIT = "LIMIT"


class TimeInForce(StrEnum):
    GTC = "GTC"
    GTD = "GTD"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELED = "CANCELED"
    REPLACE_REQUESTED = "REPLACE_REQUESTED"
    REPLACED = "REPLACED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class LiquidityRole(StrEnum):
    MAKER = "MAKER"
    TAKER = "TAKER"


class RiskDecisionType(StrEnum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    REJECT = "REJECT"


class OrderIntent(SimulationModel):
    client_order_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    token_id: str = Field(min_length=1)
    condition_id: str | None = None
    side: OrderSide
    order_type: OrderType = OrderType.LIMIT
    price: Decimal
    size: Decimal
    time_in_force: TimeInForce = TimeInForce.GTC
    post_only: bool = False
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("price")
    @classmethod
    def price_is_valid_probability(cls, value: Decimal) -> Decimal:
        if value < 0 or value > 1:
            raise ValueError("price must be between 0 and 1")
        return value

    @field_validator("size")
    @classmethod
    def size_is_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("size must be positive")
        return value

    @model_validator(mode="after")
    def gtd_orders_have_expiry(self) -> "OrderIntent":
        if self.time_in_force == TimeInForce.GTD and self.expires_at is None:
            raise ValueError("GTD orders require expires_at")
        return self


class SimulatedOrder(OrderIntent):
    remaining_size: Decimal
    status: OrderStatus = OrderStatus.PENDING
    accepted_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)
    reject_reason: str | None = None

    @field_validator("remaining_size")
    @classmethod
    def remaining_size_is_non_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("remaining_size cannot be negative")
        return value


class OrderStateTransition(SimulationModel):
    client_order_id: str = Field(min_length=1)
    from_status: OrderStatus | None = None
    to_status: OrderStatus
    reason: str
    created_at: datetime = Field(default_factory=utc_now)


class SimulatedFill(SimulationModel):
    fill_id: str = Field(min_length=1)
    client_order_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    token_id: str = Field(min_length=1)
    condition_id: str | None = None
    side: OrderSide
    price: Decimal
    size: Decimal
    fee: Decimal = Decimal("0")
    liquidity_role: LiquidityRole
    source_snapshot_id: int | None = None
    source_ts: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("price")
    @classmethod
    def fill_price_is_valid_probability(cls, value: Decimal) -> Decimal:
        if value < 0 or value > 1:
            raise ValueError("price must be between 0 and 1")
        return value

    @field_validator("size")
    @classmethod
    def fill_size_is_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("size must be positive")
        return value

    @field_validator("fee")
    @classmethod
    def fee_is_non_negative(cls, value: Decimal) -> Decimal:
        if value < 0:
            raise ValueError("fee cannot be negative")
        return value


class CashLedgerEntry(SimulationModel):
    entry_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    client_order_id: str | None = None
    fill_id: str | None = None
    delta: Decimal
    reason: str
    created_at: datetime = Field(default_factory=utc_now)


class PositionLedgerEntry(SimulationModel):
    entry_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    token_id: str = Field(min_length=1)
    condition_id: str | None = None
    client_order_id: str | None = None
    fill_id: str | None = None
    delta: Decimal
    price: Decimal
    reason: str
    created_at: datetime = Field(default_factory=utc_now)


class PositionState(SimulationModel):
    strategy_id: str = Field(min_length=1)
    token_id: str = Field(min_length=1)
    condition_id: str | None = None
    quantity: Decimal = Decimal("0")
    average_cost: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")
    fees_paid: Decimal = Decimal("0")


class ValuationSnapshot(SimulationModel):
    strategy_id: str = Field(min_length=1)
    token_id: str = Field(min_length=1)
    condition_id: str | None = None
    quantity: Decimal
    average_cost: Decimal
    mark_price: Decimal
    mark_reason: str
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    core_pnl: Decimal
    reward_pnl: Decimal = Decimal("0")
    total_pnl: Decimal
    created_at: datetime = Field(default_factory=utc_now)


class RiskCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    passed: bool
    severity: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class RiskDecision(SimulationModel):
    decision: RiskDecisionType
    client_order_id: str = Field(min_length=1)
    token_id: str = Field(min_length=1)
    condition_id: str | None = None
    checks: list[RiskCheckResult] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class SimulationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submit_latency_ms: int = 250
    cancel_latency_ms: int = 250
    conservative_queue: bool = True

    @field_validator("submit_latency_ms", "cancel_latency_ms")
    @classmethod
    def latency_is_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("latency cannot be negative")
        return value
