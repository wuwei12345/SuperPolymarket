from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from polymarket_quant.domain.simulation import (
    OrderIntent,
    OrderSide,
    RiskCheckResult,
    RiskDecision,
    RiskDecisionType,
)

INVALID_TICK_SIZE = "INVALID_TICK_SIZE"
BELOW_MIN_ORDER_SIZE = "BELOW_MIN_ORDER_SIZE"
INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
INSUFFICIENT_POSITION = "INSUFFICIENT_POSITION"
MAX_SINGLE_ORDER_EXCEEDED = "MAX_SINGLE_ORDER_EXCEEDED"
MAX_MARKET_POSITION_EXCEEDED = "MAX_MARKET_POSITION_EXCEEDED"
MAX_TOKEN_POSITION_EXCEEDED = "MAX_TOKEN_POSITION_EXCEEDED"
MARKET_NOT_ACCEPTING_ORDERS = "MARKET_NOT_ACCEPTING_ORDERS"

PORTFOLIO_EXPOSURE_WARNING = "PORTFOLIO_EXPOSURE_WARNING"
EVENT_EXPOSURE_WARNING = "EVENT_EXPOSURE_WARNING"
DRAWDOWN_WARNING = "DRAWDOWN_WARNING"
LIQUIDITY_ANOMALY_WARNING = "LIQUIDITY_ANOMALY_WARNING"


class RiskLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cash_available: Decimal
    token_position: Decimal = Decimal("0")
    max_single_order_notional: Decimal
    max_market_position: Decimal
    max_token_position: Decimal
    current_market_position: Decimal = Decimal("0")
    current_token_position: Decimal = Decimal("0")
    portfolio_exposure: Decimal = Decimal("0")
    event_exposure: Decimal = Decimal("0")
    drawdown: Decimal = Decimal("0")
    portfolio_exposure_warning: Decimal | None = None
    event_exposure_warning: Decimal | None = None
    drawdown_warning: Decimal | None = None
    liquidity_warning_spread: Decimal | None = None


class MarketConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token_id: str
    condition_id: str | None = None
    tick_size: Decimal | None = None
    min_order_size: Decimal | None = None
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None
    spread: Decimal | None = None
    active: bool = True
    accepting_orders: bool = True


def validate_order_intent(
    intent: OrderIntent, constraints: MarketConstraints
) -> list[RiskCheckResult]:
    checks: list[RiskCheckResult] = []
    if constraints.token_id != intent.token_id:
        checks.append(_hard("TOKEN_MISMATCH", "Order token does not match market constraints"))
    if intent.condition_id and constraints.condition_id:
        if intent.condition_id != constraints.condition_id:
            checks.append(
                _hard(
                    "CONDITION_MISMATCH",
                    "Order condition does not match market constraints",
                )
            )
    if not constraints.active or not constraints.accepting_orders:
        checks.append(_hard(MARKET_NOT_ACCEPTING_ORDERS, "Market is not accepting orders"))
    if constraints.tick_size is not None and constraints.tick_size > 0:
        if not _is_tick_aligned(intent.price, constraints.tick_size):
            checks.append(_hard(INVALID_TICK_SIZE, "Order price is not tick aligned"))
    if constraints.min_order_size is not None:
        if intent.size < constraints.min_order_size:
            checks.append(_hard(BELOW_MIN_ORDER_SIZE, "Order size is below minimum"))
    return checks


def apply_risk_checks(
    intent: OrderIntent, constraints: MarketConstraints, limits: RiskLimits
) -> RiskDecision:
    checks = validate_order_intent(intent, constraints)
    notional = intent.price * intent.size

    if intent.side == OrderSide.BUY and notional > limits.cash_available:
        checks.append(_hard(INSUFFICIENT_CASH, "Insufficient cash for buy order"))
    if intent.side == OrderSide.SELL and intent.size > limits.token_position:
        checks.append(_hard(INSUFFICIENT_POSITION, "Insufficient token position"))
    if notional > limits.max_single_order_notional:
        checks.append(
            _hard(MAX_SINGLE_ORDER_EXCEEDED, "Single order notional limit exceeded")
        )

    projected_market = limits.current_market_position + notional
    if projected_market > limits.max_market_position:
        checks.append(
            _hard(MAX_MARKET_POSITION_EXCEEDED, "Market position limit exceeded")
        )

    projected_token = limits.current_token_position + intent.size
    if projected_token > limits.max_token_position:
        checks.append(_hard(MAX_TOKEN_POSITION_EXCEEDED, "Token position limit exceeded"))

    warnings: list[str] = []
    if _threshold_crossed(
        limits.portfolio_exposure + notional, limits.portfolio_exposure_warning
    ):
        warnings.append(PORTFOLIO_EXPOSURE_WARNING)
        checks.append(
            _warning(PORTFOLIO_EXPOSURE_WARNING, "Portfolio exposure warning threshold")
        )
    if _threshold_crossed(limits.event_exposure + notional, limits.event_exposure_warning):
        warnings.append(EVENT_EXPOSURE_WARNING)
        checks.append(_warning(EVENT_EXPOSURE_WARNING, "Event exposure warning threshold"))
    if _threshold_crossed(limits.drawdown, limits.drawdown_warning):
        warnings.append(DRAWDOWN_WARNING)
        checks.append(_warning(DRAWDOWN_WARNING, "Drawdown warning threshold"))
    if _threshold_crossed(constraints.spread, limits.liquidity_warning_spread):
        warnings.append(LIQUIDITY_ANOMALY_WARNING)
        checks.append(_warning(LIQUIDITY_ANOMALY_WARNING, "Liquidity anomaly warning"))

    reasons = [check.code for check in checks if not check.passed and check.severity == "hard"]
    if reasons:
        decision_type = RiskDecisionType.REJECT
    elif warnings:
        decision_type = RiskDecisionType.WARN
    else:
        decision_type = RiskDecisionType.ALLOW

    return RiskDecision(
        decision=decision_type,
        client_order_id=intent.client_order_id,
        token_id=intent.token_id,
        condition_id=intent.condition_id or constraints.condition_id,
        checks=checks,
        reasons=reasons,
        warnings=warnings,
    )


def _is_tick_aligned(price: Decimal, tick_size: Decimal) -> bool:
    return (price % tick_size).normalize() == Decimal("0")


def _threshold_crossed(value: Decimal | None, threshold: Decimal | None) -> bool:
    return value is not None and threshold is not None and value > threshold


def _hard(code: str, message: str) -> RiskCheckResult:
    return RiskCheckResult(code=code, passed=False, severity="hard", message=message)


def _warning(code: str, message: str) -> RiskCheckResult:
    return RiskCheckResult(code=code, passed=False, severity="warning", message=message)
