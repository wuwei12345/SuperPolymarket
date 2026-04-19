from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from polymarket_quant.domain.simulation import (
    OrderIntent,
    OrderSide,
    OrderStatus,
)
from polymarket_quant.services.order_lifecycle import OrderLifecycleService
from polymarket_quant.services.order_risk import (
    INSUFFICIENT_CASH,
    INVALID_TICK_SIZE,
    LIQUIDITY_ANOMALY_WARNING,
    MarketConstraints,
    PORTFOLIO_EXPOSURE_WARNING,
    RiskLimits,
    apply_risk_checks,
)


def instant() -> datetime:
    return datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc)


def intent(**overrides: object) -> OrderIntent:
    values = {
        "client_order_id": "order-1",
        "strategy_id": "strategy-a",
        "token_id": "token-yes",
        "condition_id": "0xcondition",
        "side": OrderSide.BUY,
        "price": Decimal("0.45"),
        "size": Decimal("10"),
        "created_at": instant(),
    }
    values.update(overrides)
    return OrderIntent(**values)


def constraints(**overrides: object) -> MarketConstraints:
    values = {
        "token_id": "token-yes",
        "condition_id": "0xcondition",
        "tick_size": Decimal("0.01"),
        "min_order_size": Decimal("1"),
        "best_bid": Decimal("0.44"),
        "best_ask": Decimal("0.46"),
        "spread": Decimal("0.02"),
    }
    values.update(overrides)
    return MarketConstraints(**values)


def limits(**overrides: object) -> RiskLimits:
    values = {
        "cash_available": Decimal("100"),
        "token_position": Decimal("100"),
        "max_single_order_notional": Decimal("50"),
        "max_market_position": Decimal("100"),
        "max_token_position": Decimal("200"),
    }
    values.update(overrides)
    return RiskLimits(**values)


def test_lifecycle_rejects_filled_to_canceled_transition() -> None:
    lifecycle = OrderLifecycleService()
    order = lifecycle.create_order(intent(), now=instant())
    order, _ = lifecycle.transition(order, OrderStatus.ACCEPTED, "accepted", instant())
    order, _ = lifecycle.mark_open(order, now=instant())
    order, _ = lifecycle.mark_filled(order, now=instant())

    with pytest.raises(ValueError, match="invalid order transition"):
        lifecycle.cancel(order, now=instant())


def test_lifecycle_supports_cancel_and_replace_requests() -> None:
    lifecycle = OrderLifecycleService()
    order = lifecycle.create_order(intent(), now=instant())
    order, _ = lifecycle.transition(order, OrderStatus.ACCEPTED, "accepted", instant())
    order, _ = lifecycle.mark_open(order, now=instant())

    cancel_requested, cancel_transition = lifecycle.request_cancel(order, now=instant())
    assert cancel_requested.status == OrderStatus.CANCEL_REQUESTED
    assert cancel_transition.to_status == OrderStatus.CANCEL_REQUESTED

    order = lifecycle.create_order(
        intent(client_order_id="order-2"), now=instant()
    )
    order, _ = lifecycle.transition(order, OrderStatus.ACCEPTED, "accepted", instant())
    order, _ = lifecycle.mark_open(order, now=instant())
    replace_requested, replace_transition = lifecycle.request_replace(order, now=instant())
    assert replace_requested.status == OrderStatus.REPLACE_REQUESTED
    assert replace_transition.to_status == OrderStatus.REPLACE_REQUESTED


def test_risk_rejects_invalid_tick_size() -> None:
    decision = apply_risk_checks(
        intent(price=Decimal("0.455")),
        constraints(),
        limits(),
    )

    assert decision.decision == "REJECT"
    assert INVALID_TICK_SIZE in decision.reasons


def test_risk_rejects_insufficient_cash_for_buy() -> None:
    decision = apply_risk_checks(
        intent(price=Decimal("0.90"), size=Decimal("20")),
        constraints(),
        limits(cash_available=Decimal("5")),
    )

    assert decision.decision == "REJECT"
    assert INSUFFICIENT_CASH in decision.reasons


def test_risk_rejects_sell_without_position() -> None:
    decision = apply_risk_checks(
        intent(side=OrderSide.SELL, size=Decimal("20")),
        constraints(),
        limits(token_position=Decimal("1")),
    )

    assert decision.decision == "REJECT"
    assert "INSUFFICIENT_POSITION" in decision.reasons


def test_warning_checks_do_not_hard_reject_order() -> None:
    decision = apply_risk_checks(
        intent(),
        constraints(spread=Decimal("0.12")),
        limits(
            portfolio_exposure=Decimal("90"),
            portfolio_exposure_warning=Decimal("91"),
            liquidity_warning_spread=Decimal("0.10"),
        ),
    )

    assert decision.decision == "WARN"
    assert PORTFOLIO_EXPOSURE_WARNING in decision.warnings
    assert LIQUIDITY_ANOMALY_WARNING in decision.warnings
    assert decision.reasons == []


def test_hard_reject_takes_priority_over_warnings() -> None:
    decision = apply_risk_checks(
        intent(price=Decimal("0.455")),
        constraints(spread=Decimal("0.12")),
        limits(liquidity_warning_spread=Decimal("0.10")),
    )

    assert decision.decision == "REJECT"
    assert INVALID_TICK_SIZE in decision.reasons
    assert LIQUIDITY_ANOMALY_WARNING in decision.warnings
