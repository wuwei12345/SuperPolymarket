from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from polymarket_quant.domain.market_data import BookLevel, BookSnapshot
from polymarket_quant.domain.simulation import (
    OrderSide,
    OrderStatus,
    OrderType,
    SimulatedOrder,
    TimeInForce,
)
from polymarket_quant.services.fill_engine import (
    CONSERVATIVE_QUEUE_WAIT,
    NO_CROSS,
    SUBMIT_LATENCY_PENDING,
    FillEngineConfig,
    is_cancel_effective,
    simulate_fills,
)


def instant() -> datetime:
    return datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc)


def order(**overrides: object) -> SimulatedOrder:
    values = {
        "client_order_id": "order-1",
        "strategy_id": "strategy-a",
        "token_id": "token-yes",
        "condition_id": "0xcondition",
        "side": OrderSide.BUY,
        "order_type": OrderType.LIMIT,
        "price": Decimal("0.50"),
        "size": Decimal("10"),
        "remaining_size": Decimal("10"),
        "status": OrderStatus.OPEN,
        "time_in_force": TimeInForce.GTC,
        "created_at": instant(),
        "updated_at": instant(),
    }
    values.update(overrides)
    return SimulatedOrder(**values)


def book() -> BookSnapshot:
    return BookSnapshot(
        token_id="token-yes",
        condition_id="0xcondition",
        source_ts=instant(),
        received_at=instant(),
        bids=[
            BookLevel(side="BUY", price=Decimal("0.44"), size=Decimal("2")),
            BookLevel(side="BUY", price=Decimal("0.43"), size=Decimal("10")),
        ],
        asks=[
            BookLevel(side="SELL", price=Decimal("0.46"), size=Decimal("3")),
            BookLevel(side="SELL", price=Decimal("0.48"), size=Decimal("4")),
            BookLevel(side="SELL", price=Decimal("0.52"), size=Decimal("20")),
        ],
    )


def effective_config() -> FillEngineConfig:
    return FillEngineConfig(submit_latency_ms=0, cancel_latency_ms=250)


def test_marketable_buy_consumes_asks_by_price() -> None:
    result = simulate_fills(
        order(price=Decimal("0.48"), remaining_size=Decimal("6")),
        book(),
        effective_config(),
        now=instant(),
    )

    assert [fill.price for fill in result.fills] == [
        Decimal("0.46"),
        Decimal("0.48"),
    ]
    assert result.filled_size == Decimal("6")
    assert result.status == OrderStatus.FILLED


def test_marketable_sell_consumes_bids_by_price() -> None:
    result = simulate_fills(
        order(
            side=OrderSide.SELL,
            price=Decimal("0.43"),
            remaining_size=Decimal("3"),
        ),
        book(),
        effective_config(),
        now=instant(),
    )

    assert [fill.price for fill in result.fills] == [
        Decimal("0.44"),
        Decimal("0.43"),
    ]
    assert result.filled_size == Decimal("3")
    assert result.status == OrderStatus.FILLED


def test_partial_fill_leaves_residual_open() -> None:
    result = simulate_fills(
        order(price=Decimal("0.48"), remaining_size=Decimal("10")),
        book(),
        effective_config(),
        now=instant(),
    )

    assert result.filled_size == Decimal("7")
    assert result.remaining_size == Decimal("3")
    assert result.status == OrderStatus.PARTIALLY_FILLED


def test_non_crossing_limit_order_remains_open() -> None:
    result = simulate_fills(
        order(price=Decimal("0.45")),
        book(),
        FillEngineConfig(submit_latency_ms=0, conservative_queue=False),
        now=instant(),
    )

    assert result.fills == []
    assert result.status == OrderStatus.OPEN
    assert result.reason == NO_CROSS


def test_full_fill_sets_remaining_size_to_zero() -> None:
    result = simulate_fills(
        order(price=Decimal("0.48"), remaining_size=Decimal("7")),
        book(),
        effective_config(),
        now=instant(),
    )

    assert result.remaining_size == Decimal("0")
    assert result.status == OrderStatus.FILLED


def test_submit_latency_blocks_immediate_fill() -> None:
    result = simulate_fills(
        order(created_at=instant(), price=Decimal("0.48")),
        book(),
        FillEngineConfig(submit_latency_ms=500),
        now=instant() + timedelta(milliseconds=100),
    )

    assert result.fills == []
    assert result.reason == SUBMIT_LATENCY_PENDING


def test_cancel_latency_helper_requires_delay() -> None:
    requested = instant()
    config = FillEngineConfig(cancel_latency_ms=250)

    assert not is_cancel_effective(
        requested, requested + timedelta(milliseconds=100), config
    )
    assert is_cancel_effective(requested, requested + timedelta(milliseconds=250), config)


def test_conservative_queue_does_not_fill_resting_order_from_same_snapshot() -> None:
    result = simulate_fills(
        order(price=Decimal("0.45")),
        book(),
        FillEngineConfig(submit_latency_ms=0, conservative_queue=True),
        now=instant(),
    )

    assert result.fills == []
    assert result.status == OrderStatus.OPEN
    assert result.reason == CONSERVATIVE_QUEUE_WAIT
