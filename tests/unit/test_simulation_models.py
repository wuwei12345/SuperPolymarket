from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from polymarket_quant.domain.simulation import (
    LiquidityRole,
    OrderIntent,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskCheckResult,
    RiskDecision,
    RiskDecisionType,
    SimulatedFill,
    SimulatedOrder,
    TimeInForce,
    ValuationSnapshot,
)


def instant() -> datetime:
    return datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc)


def order_intent(**overrides: object) -> OrderIntent:
    values = {
        "client_order_id": "order-1",
        "strategy_id": "strategy-a",
        "token_id": "token-yes",
        "condition_id": "0xcondition",
        "side": OrderSide.BUY,
        "order_type": OrderType.LIMIT,
        "price": Decimal("0.45"),
        "size": Decimal("10"),
        "created_at": instant(),
    }
    values.update(overrides)
    return OrderIntent(**values)


def test_order_intent_rejects_blank_client_order_id() -> None:
    with pytest.raises(ValidationError):
        order_intent(client_order_id=" ")


def test_order_intent_rejects_price_above_one() -> None:
    with pytest.raises(ValidationError):
        order_intent(price=Decimal("1.01"))


def test_order_intent_rejects_non_positive_size() -> None:
    with pytest.raises(ValidationError):
        order_intent(size=Decimal("0"))


def test_gtd_order_requires_expiry() -> None:
    with pytest.raises(ValidationError):
        order_intent(time_in_force=TimeInForce.GTD)


def test_simulated_order_tracks_remaining_size_and_status() -> None:
    intent = order_intent()
    order = SimulatedOrder(
        **intent.model_dump(),
        remaining_size=Decimal("10"),
        status=OrderStatus.OPEN,
        updated_at=instant(),
    )

    assert order.client_order_id == "order-1"
    assert order.remaining_size == Decimal("10")
    assert order.status == OrderStatus.OPEN


def test_simulated_fill_rejects_negative_fee() -> None:
    with pytest.raises(ValidationError):
        SimulatedFill(
            fill_id="fill-1",
            client_order_id="order-1",
            strategy_id="strategy-a",
            token_id="token-yes",
            side=OrderSide.BUY,
            price=Decimal("0.50"),
            size=Decimal("1"),
            fee=Decimal("-0.01"),
            liquidity_role=LiquidityRole.TAKER,
        )


def test_risk_decision_keeps_reasons_and_warnings_structured() -> None:
    decision = RiskDecision(
        decision=RiskDecisionType.WARN,
        client_order_id="order-1",
        token_id="token-yes",
        condition_id="0xcondition",
        checks=[
            RiskCheckResult(
                code="PORTFOLIO_EXPOSURE_WARNING",
                passed=False,
                severity="warning",
                message="Portfolio exposure warning",
            )
        ],
        warnings=["PORTFOLIO_EXPOSURE_WARNING"],
    )

    assert decision.decision == RiskDecisionType.WARN
    assert decision.warnings == ["PORTFOLIO_EXPOSURE_WARNING"]
    assert decision.reasons == []


def test_valuation_snapshot_separates_core_and_reward_pnl() -> None:
    snapshot = ValuationSnapshot(
        strategy_id="strategy-a",
        token_id="token-yes",
        condition_id="0xcondition",
        quantity=Decimal("10"),
        average_cost=Decimal("0.40"),
        mark_price=Decimal("0.45"),
        mark_reason="BEST_BID",
        realized_pnl=Decimal("1"),
        unrealized_pnl=Decimal("0.5"),
        core_pnl=Decimal("1.5"),
        reward_pnl=Decimal("0.2"),
        total_pnl=Decimal("1.5"),
        created_at=instant(),
    )

    assert snapshot.core_pnl == Decimal("1.5")
    assert snapshot.reward_pnl == Decimal("0.2")
    assert snapshot.total_pnl == snapshot.core_pnl
