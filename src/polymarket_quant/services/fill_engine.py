from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from polymarket_quant.domain.market_data import BookLevel, BookSnapshot, utc_now
from polymarket_quant.domain.simulation import (
    LiquidityRole,
    OrderSide,
    OrderStatus,
    SimulatedFill,
    SimulatedOrder,
)

SUBMIT_LATENCY_PENDING = "SUBMIT_LATENCY_PENDING"
CONSERVATIVE_QUEUE_WAIT = "CONSERVATIVE_QUEUE_WAIT"
NO_CROSS = "NO_CROSS"
FILLED = "FILLED"
PARTIALLY_FILLED = "PARTIALLY_FILLED"


class FillEngineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    submit_latency_ms: int = 250
    cancel_latency_ms: int = 250
    conservative_queue: bool = True


class FillSimulationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fills: list[SimulatedFill] = Field(default_factory=list)
    remaining_size: Decimal
    filled_size: Decimal
    status: OrderStatus
    reason: str


def is_submission_effective(
    order: SimulatedOrder, now: datetime, config: FillEngineConfig
) -> bool:
    return now >= order.created_at + timedelta(milliseconds=config.submit_latency_ms)


def is_cancel_effective(
    cancel_requested_at: datetime, now: datetime, config: FillEngineConfig
) -> bool:
    return now >= cancel_requested_at + timedelta(milliseconds=config.cancel_latency_ms)


def simulate_fills(
    order: SimulatedOrder,
    snapshot: BookSnapshot,
    config: FillEngineConfig,
    now: datetime | None = None,
) -> FillSimulationResult:
    timestamp = now or utc_now()
    if not is_submission_effective(order, timestamp, config):
        return FillSimulationResult(
            fills=[],
            remaining_size=order.remaining_size,
            filled_size=Decimal("0"),
            status=OrderStatus.OPEN,
            reason=SUBMIT_LATENCY_PENDING,
        )

    eligible_levels = _eligible_levels(order, snapshot)
    if not eligible_levels:
        reason = CONSERVATIVE_QUEUE_WAIT if config.conservative_queue else NO_CROSS
        return FillSimulationResult(
            fills=[],
            remaining_size=order.remaining_size,
            filled_size=Decimal("0"),
            status=OrderStatus.OPEN,
            reason=reason,
        )

    remaining = order.remaining_size
    fills: list[SimulatedFill] = []
    for level in eligible_levels:
        if remaining <= 0:
            break
        fill_size = min(remaining, level.size)
        fills.append(
            SimulatedFill(
                fill_id=f"fill-{uuid4().hex}",
                client_order_id=order.client_order_id,
                strategy_id=order.strategy_id,
                token_id=order.token_id,
                condition_id=order.condition_id,
                side=order.side,
                price=level.price,
                size=fill_size,
                fee=Decimal("0"),
                liquidity_role=LiquidityRole.TAKER,
                source_snapshot_id=None,
                source_ts=snapshot.source_ts,
                created_at=timestamp,
            )
        )
        remaining -= fill_size

    filled_size = order.remaining_size - remaining
    if remaining == 0:
        status = OrderStatus.FILLED
        reason = FILLED
    elif filled_size > 0:
        status = OrderStatus.PARTIALLY_FILLED
        reason = PARTIALLY_FILLED
    else:
        status = OrderStatus.OPEN
        reason = NO_CROSS

    return FillSimulationResult(
        fills=fills,
        remaining_size=remaining,
        filled_size=filled_size,
        status=status,
        reason=reason,
    )


def _eligible_levels(order: SimulatedOrder, snapshot: BookSnapshot) -> list[BookLevel]:
    if order.side == OrderSide.BUY:
        levels = sorted(snapshot.asks, key=lambda level: level.price)
        return [level for level in levels if level.price <= order.price]
    levels = sorted(snapshot.bids, key=lambda level: level.price, reverse=True)
    return [level for level in levels if level.price >= order.price]
