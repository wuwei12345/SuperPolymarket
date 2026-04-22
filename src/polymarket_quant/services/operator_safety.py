from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polymarket_quant.domain.market_data import utc_now
from polymarket_quant.domain.operator import (
    AlertSeverity,
    AlertSummary,
    ConnectionComponent,
    ConnectionState,
    ConnectionStatus,
    GlobalMode,
    NewOrderBlockState,
)

THREE_PERCENT = Decimal("0.03")
FIVE_PERCENT = Decimal("0.05")


class OperatorSafetyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SafetyAlertScope(StrEnum):
    DISPLAY_ONLY = "display_only"
    INCREASE_EXPOSURE = "increase_exposure"
    ALL_NEW_ORDERS = "all_new_orders"


class OrderAction(StrEnum):
    INCREASE_EXPOSURE = "increase_exposure"
    REDUCE = "reduce"
    CLOSE = "close"
    RISK_RELEASE = "risk_release"
    CANCEL = "cancel"
    REPLACE = "replace"


class OperatorSafetyAlert(OperatorSafetyModel):
    code: str
    severity: AlertSeverity
    message: str
    scope: SafetyAlertScope = SafetyAlertScope.DISPLAY_ONLY
    details: dict[str, Any] = Field(default_factory=dict)


class OperatorSafetySnapshot(OperatorSafetyModel):
    token_id: str
    condition_id: str | None = None
    now: datetime = Field(default_factory=utc_now)
    end_date: datetime | None = None
    active: bool = True
    accepting_orders: bool = True
    mode_available: bool = True
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None
    tick_size: Decimal = Decimal("0.01")
    min_order_size: Decimal = Decimal("1")
    top_of_book_depth_usdc: Decimal | None = None
    bid_depth_usdc: Decimal | None = None
    ask_depth_usdc: Decimal | None = None
    last_trade_at: datetime | None = None
    gap_fill_events_per_minute: Decimal = Decimal("0")
    connections: list[ConnectionState] = Field(default_factory=list)


class OperatorSafetyEvaluation(OperatorSafetyModel):
    alerts: list[OperatorSafetyAlert] = Field(default_factory=list)
    new_order_status: NewOrderBlockState = NewOrderBlockState.ALLOWED
    alert_summary: AlertSummary = Field(default_factory=AlertSummary)


class ActionGateDecision(OperatorSafetyModel):
    action: OrderAction
    allowed: bool
    block_state: NewOrderBlockState
    reasons: list[str] = Field(default_factory=list)


class ModePreflightResult(OperatorSafetyModel):
    current_mode: GlobalMode
    target_mode: GlobalMode
    allowed: bool
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True


class OperatorSafetyService:
    def evaluate(self, snapshot: OperatorSafetySnapshot) -> OperatorSafetyEvaluation:
        alerts: list[OperatorSafetyAlert] = []
        alerts.extend(self._market_state_alerts(snapshot))
        alerts.extend(self._connection_alerts(snapshot.connections))
        alerts.extend(self._expiry_alerts(snapshot))
        alerts.extend(self._liquidity_alerts(snapshot))
        summary = _alert_summary(alerts)
        return OperatorSafetyEvaluation(
            alerts=alerts,
            new_order_status=_derive_block_state(alerts),
            alert_summary=summary,
        )

    def gate_action(
        self,
        evaluation: OperatorSafetyEvaluation,
        action: OrderAction,
    ) -> ActionGateDecision:
        full_blockers = [
            alert.code
            for alert in evaluation.alerts
            if alert.severity == AlertSeverity.CRITICAL
            and alert.scope == SafetyAlertScope.ALL_NEW_ORDERS
        ]
        partial_blockers = [
            alert.code
            for alert in evaluation.alerts
            if alert.severity == AlertSeverity.CRITICAL
            and alert.scope == SafetyAlertScope.INCREASE_EXPOSURE
        ]

        if action == OrderAction.CANCEL:
            return ActionGateDecision(
                action=action,
                allowed=True,
                block_state=evaluation.new_order_status,
            )
        if full_blockers:
            return ActionGateDecision(
                action=action,
                allowed=False,
                block_state=NewOrderBlockState.FULLY_BLOCKED,
                reasons=full_blockers,
            )
        if partial_blockers and action not in {
            OrderAction.REDUCE,
            OrderAction.CLOSE,
            OrderAction.RISK_RELEASE,
        }:
            return ActionGateDecision(
                action=action,
                allowed=False,
                block_state=NewOrderBlockState.PARTIALLY_BLOCKED,
                reasons=partial_blockers,
            )
        return ActionGateDecision(
            action=action,
            allowed=True,
            block_state=evaluation.new_order_status,
        )

    def preflight(
        self,
        *,
        current_mode: GlobalMode,
        target_mode: GlobalMode,
        connections: list[ConnectionState],
        evaluation: OperatorSafetyEvaluation | None = None,
    ) -> ModePreflightResult:
        blockers: list[str] = []
        warnings: list[str] = []

        if target_mode == GlobalMode.LIVE_DISABLED:
            warnings.append("Target mode is live-disabled; this is a protective boundary.")
            return ModePreflightResult(
                current_mode=current_mode,
                target_mode=target_mode,
                allowed=True,
                blockers=[],
                warnings=warnings,
            )

        connection_map = {state.component: state for state in connections}
        required_components = {
            ConnectionComponent.DB,
            ConnectionComponent.RISK,
        }
        if target_mode == GlobalMode.PAPER:
            required_components.update(
                {
                    ConnectionComponent.MARKET_DATA_WS,
                    ConnectionComponent.EXECUTION,
                }
            )

        missing = sorted(
            component.value
            for component in required_components
            if component not in connection_map
        )
        if missing:
            blockers.append(
                f"Missing required connections for {target_mode.value}: {', '.join(missing)}"
            )

        for component in required_components:
            state = connection_map.get(component)
            if state is None:
                continue
            if state.status == ConnectionStatus.DOWN:
                blockers.append(
                    f"{component.value} is down; cannot switch to {target_mode.value}"
                )
            elif state.status == ConnectionStatus.DEGRADED:
                warnings.append(
                    f"{component.value} is degraded while preparing {target_mode.value}"
                )

        if evaluation is not None:
            for alert in evaluation.alerts:
                if alert.severity == AlertSeverity.CRITICAL:
                    blockers.append(f"{alert.code}: {alert.message}")
                elif alert.severity == AlertSeverity.WARNING:
                    warnings.append(f"{alert.code}: {alert.message}")

        return ModePreflightResult(
            current_mode=current_mode,
            target_mode=target_mode,
            allowed=not blockers,
            blockers=blockers,
            warnings=warnings,
        )

    def _market_state_alerts(
        self, snapshot: OperatorSafetySnapshot
    ) -> list[OperatorSafetyAlert]:
        alerts: list[OperatorSafetyAlert] = []
        if not snapshot.active:
            alerts.append(
                OperatorSafetyAlert(
                    code="MARKET_CLOSED",
                    severity=AlertSeverity.CRITICAL,
                    message="Market is closed.",
                    scope=SafetyAlertScope.ALL_NEW_ORDERS,
                )
            )
        if not snapshot.accepting_orders:
            alerts.append(
                OperatorSafetyAlert(
                    code="MARKET_NOT_ACCEPTING_ORDERS",
                    severity=AlertSeverity.CRITICAL,
                    message="Market is not accepting orders.",
                    scope=SafetyAlertScope.ALL_NEW_ORDERS,
                )
            )
        if not snapshot.mode_available:
            alerts.append(
                OperatorSafetyAlert(
                    code="MODE_UNAVAILABLE",
                    severity=AlertSeverity.CRITICAL,
                    message="Requested mode is unavailable; live-disabled remains a boundary.",
                    scope=SafetyAlertScope.ALL_NEW_ORDERS,
                )
            )
        return alerts

    def _connection_alerts(
        self, connections: list[ConnectionState]
    ) -> list[OperatorSafetyAlert]:
        alerts: list[OperatorSafetyAlert] = []
        connection_map = {state.component: state for state in connections}
        required = {
            ConnectionComponent.DB,
            ConnectionComponent.MARKET_DATA_WS,
            ConnectionComponent.EXECUTION,
            ConnectionComponent.RISK,
        }
        missing = sorted(component.value for component in required if component not in connection_map)
        if missing:
            alerts.append(
                OperatorSafetyAlert(
                    code="KEY_CONNECTION_INCOMPLETE",
                    severity=AlertSeverity.CRITICAL,
                    message=f"Missing key connections: {', '.join(missing)}",
                    scope=SafetyAlertScope.ALL_NEW_ORDERS,
                )
            )
        for state in connections:
            if state.status == ConnectionStatus.DOWN:
                alerts.append(
                    OperatorSafetyAlert(
                        code=f"{state.component.value}_DOWN",
                        severity=AlertSeverity.CRITICAL,
                        message=f"{state.component.value} connection is down.",
                        scope=SafetyAlertScope.ALL_NEW_ORDERS,
                    )
                )
            elif state.status == ConnectionStatus.DEGRADED:
                alerts.append(
                    OperatorSafetyAlert(
                        code=f"{state.component.value}_DEGRADED",
                        severity=AlertSeverity.WARNING,
                        message=f"{state.component.value} connection is degraded.",
                    )
                )
        return alerts

    def _expiry_alerts(
        self, snapshot: OperatorSafetySnapshot
    ) -> list[OperatorSafetyAlert]:
        if snapshot.end_date is None:
            return []
        minutes_to_expiry = Decimal(
            str((snapshot.end_date - snapshot.now).total_seconds() / 60)
        )
        if minutes_to_expiry < Decimal("15"):
            return [
                OperatorSafetyAlert(
                    code="EXPIRY_CRITICAL",
                    severity=AlertSeverity.CRITICAL,
                    message="Time to expiry is below 15 minutes.",
                    scope=SafetyAlertScope.INCREASE_EXPOSURE,
                    details={"minutes_to_expiry": float(minutes_to_expiry)},
                )
            ]
        if minutes_to_expiry < Decimal("60"):
            return [
                OperatorSafetyAlert(
                    code="EXPIRY_WARNING",
                    severity=AlertSeverity.WARNING,
                    message="Time to expiry is below 60 minutes.",
                    details={"minutes_to_expiry": float(minutes_to_expiry)},
                )
            ]
        if minutes_to_expiry < Decimal("120"):
            return [
                OperatorSafetyAlert(
                    code="EXPIRY_INFO",
                    severity=AlertSeverity.INFO,
                    message="Time to expiry is below 120 minutes.",
                    details={"minutes_to_expiry": float(minutes_to_expiry)},
                )
            ]
        return []

    def _liquidity_alerts(
        self, snapshot: OperatorSafetySnapshot
    ) -> list[OperatorSafetyAlert]:
        alerts: list[OperatorSafetyAlert] = []
        threshold_details = {
            "warning_threshold": "max(3 ticks, 3%)",
            "critical_threshold": "max(5 ticks, 5%)",
        }
        # Warning threshold: max(3 ticks, 3%)
        warning_spread_limit = max(snapshot.tick_size * 3, THREE_PERCENT)
        # Critical threshold: max(5 ticks, 5%)
        critical_spread_limit = max(snapshot.tick_size * 5, FIVE_PERCENT)

        spread = None
        if snapshot.best_bid is not None and snapshot.best_ask is not None:
            spread = snapshot.best_ask - snapshot.best_bid
        if spread is not None:
            if spread > critical_spread_limit:
                alerts.append(
                    OperatorSafetyAlert(
                        code="LIQUIDITY_SPREAD_CRITICAL",
                        severity=AlertSeverity.CRITICAL,
                        message="Spread breached the critical liquidity threshold.",
                        scope=SafetyAlertScope.INCREASE_EXPOSURE,
                        details={
                            **threshold_details,
                            "spread": str(spread),
                        },
                    )
                )
            elif spread > warning_spread_limit:
                alerts.append(
                    OperatorSafetyAlert(
                        code="LIQUIDITY_SPREAD_WARNING",
                        severity=AlertSeverity.WARNING,
                        message="Spread breached the warning liquidity threshold.",
                        details={
                            **threshold_details,
                            "spread": str(spread),
                        },
                    )
                )

        top_of_book_depth_usdc = snapshot.top_of_book_depth_usdc
        if top_of_book_depth_usdc is None:
            top_of_book_depth_usdc = _infer_top_of_book_depth(snapshot)
        if top_of_book_depth_usdc is not None:
            if top_of_book_depth_usdc < snapshot.min_order_size:
                alerts.append(
                    OperatorSafetyAlert(
                        code="LIQUIDITY_DEPTH_CRITICAL",
                        severity=AlertSeverity.CRITICAL,
                        message="top_of_book_depth_usdc is below 1x min order size.",
                        scope=SafetyAlertScope.INCREASE_EXPOSURE,
                        details={"top_of_book_depth_usdc": str(top_of_book_depth_usdc)},
                    )
                )
            elif top_of_book_depth_usdc < snapshot.min_order_size * 2:
                alerts.append(
                    OperatorSafetyAlert(
                        code="LIQUIDITY_DEPTH_WARNING",
                        severity=AlertSeverity.WARNING,
                        message="top_of_book_depth_usdc is below 2x min order size.",
                        details={"top_of_book_depth_usdc": str(top_of_book_depth_usdc)},
                    )
                )

        if snapshot.last_trade_at is None:
            minutes_since_trade = Decimal("Infinity")
        else:
            minutes_since_trade = Decimal(
                str((snapshot.now - snapshot.last_trade_at).total_seconds() / 60)
            )
        if minutes_since_trade >= Decimal("15"):
            alerts.append(
                OperatorSafetyAlert(
                    code="ACTIVITY_CRITICAL",
                    severity=AlertSeverity.CRITICAL,
                    message="No recent trade in the last 15 minutes.",
                    scope=SafetyAlertScope.INCREASE_EXPOSURE,
                    details={"minutes_since_trade": float(minutes_since_trade)},
                )
            )
        elif minutes_since_trade >= Decimal("5"):
            alerts.append(
                OperatorSafetyAlert(
                    code="ACTIVITY_WARNING",
                    severity=AlertSeverity.WARNING,
                    message="No recent trade in the last 5 minutes.",
                    details={"minutes_since_trade": float(minutes_since_trade)},
                )
            )

        if snapshot.gap_fill_events_per_minute > Decimal("3"):
            alerts.append(
                OperatorSafetyAlert(
                    code="GAP_FILL_CRITICAL",
                    severity=AlertSeverity.CRITICAL,
                    message="gap_fill instability exceeds 3 events per minute.",
                    scope=SafetyAlertScope.INCREASE_EXPOSURE,
                    details={"gap_fill_events_per_minute": str(snapshot.gap_fill_events_per_minute)},
                )
            )
        elif snapshot.gap_fill_events_per_minute > 0:
            alerts.append(
                OperatorSafetyAlert(
                    code="GAP_FILL_WARNING",
                    severity=AlertSeverity.WARNING,
                    message="gap_fill instability is present.",
                    details={"gap_fill_events_per_minute": str(snapshot.gap_fill_events_per_minute)},
                )
            )

        book_alert = _book_integrity_alert(snapshot)
        if book_alert is not None:
            alerts.append(book_alert)
        return alerts


def _infer_top_of_book_depth(snapshot: OperatorSafetySnapshot) -> Decimal | None:
    depths = [
        depth
        for depth in (snapshot.bid_depth_usdc, snapshot.ask_depth_usdc)
        if depth is not None
    ]
    if not depths:
        return None
    return min(depths)


def _book_integrity_alert(
    snapshot: OperatorSafetySnapshot,
) -> OperatorSafetyAlert | None:
    if snapshot.best_bid is None and snapshot.best_ask is None:
        return OperatorSafetyAlert(
            code="BOOK_CRITICAL",
            severity=AlertSeverity.CRITICAL,
            message="Book is missing both sides.",
            scope=SafetyAlertScope.INCREASE_EXPOSURE,
        )
    if snapshot.best_bid is None or snapshot.best_ask is None:
        return OperatorSafetyAlert(
            code="BOOK_WARNING",
            severity=AlertSeverity.WARNING,
            message="Book is missing one side.",
        )
    if snapshot.bid_depth_usdc is None or snapshot.ask_depth_usdc is None:
        return OperatorSafetyAlert(
            code="BOOK_WARNING",
            severity=AlertSeverity.WARNING,
            message="Book top-of-book depth is missing one side.",
        )
    smaller_depth = min(snapshot.bid_depth_usdc, snapshot.ask_depth_usdc)
    larger_depth = max(snapshot.bid_depth_usdc, snapshot.ask_depth_usdc)
    if smaller_depth == 0 or (smaller_depth > 0 and larger_depth / smaller_depth >= 10):
        return OperatorSafetyAlert(
            code="BOOK_CRITICAL",
            severity=AlertSeverity.CRITICAL,
            message="Book shows severe imbalance.",
            scope=SafetyAlertScope.INCREASE_EXPOSURE,
        )
    return None


def _alert_summary(alerts: list[OperatorSafetyAlert]) -> AlertSummary:
    summary = AlertSummary()
    for alert in alerts:
        if alert.severity == AlertSeverity.INFO:
            summary.Info += 1
        elif alert.severity == AlertSeverity.WARNING:
            summary.Warning += 1
        elif alert.severity == AlertSeverity.CRITICAL:
            summary.Critical += 1
    return summary


def _derive_block_state(
    alerts: list[OperatorSafetyAlert],
) -> NewOrderBlockState:
    if any(
        alert.severity == AlertSeverity.CRITICAL
        and alert.scope == SafetyAlertScope.ALL_NEW_ORDERS
        for alert in alerts
    ):
        return NewOrderBlockState.FULLY_BLOCKED
    if any(
        alert.severity == AlertSeverity.CRITICAL
        and alert.scope == SafetyAlertScope.INCREASE_EXPOSURE
        for alert in alerts
    ):
        return NewOrderBlockState.PARTIALLY_BLOCKED
    return NewOrderBlockState.ALLOWED
