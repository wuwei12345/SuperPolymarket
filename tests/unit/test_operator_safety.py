from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from polymarket_quant.domain.operator import (
    AlertSeverity,
    ConnectionComponent,
    ConnectionState,
    ConnectionStatus,
    GlobalMode,
    NewOrderBlockState,
)
from polymarket_quant.services.operator_safety import (
    OperatorSafetyService,
    OperatorSafetySnapshot,
    OrderAction,
)


def instant() -> datetime:
    return datetime(2026, 4, 22, 8, 0, tzinfo=timezone.utc)


def healthy_connections() -> list[ConnectionState]:
    now = instant()
    return [
        ConnectionState(
            component=ConnectionComponent.DB,
            status=ConnectionStatus.HEALTHY,
            updated_at=now,
        ),
        ConnectionState(
            component=ConnectionComponent.MARKET_DATA_WS,
            status=ConnectionStatus.HEALTHY,
            updated_at=now,
        ),
        ConnectionState(
            component=ConnectionComponent.EXECUTION,
            status=ConnectionStatus.HEALTHY,
            updated_at=now,
        ),
        ConnectionState(
            component=ConnectionComponent.RISK,
            status=ConnectionStatus.HEALTHY,
            updated_at=now,
        ),
    ]


def snapshot(**overrides: object) -> OperatorSafetySnapshot:
    values: dict[str, object] = {
        "token_id": "token-yes",
        "condition_id": "condition-1",
        "now": instant(),
        "end_date": instant() + timedelta(minutes=180),
        "active": True,
        "accepting_orders": True,
        "mode_available": True,
        "best_bid": Decimal("0.49"),
        "best_ask": Decimal("0.51"),
        "tick_size": Decimal("0.01"),
        "min_order_size": Decimal("1"),
        "top_of_book_depth_usdc": Decimal("10"),
        "bid_depth_usdc": Decimal("10"),
        "ask_depth_usdc": Decimal("10"),
        "last_trade_at": instant() - timedelta(minutes=1),
        "gap_fill_events_per_minute": Decimal("0"),
        "connections": healthy_connections(),
    }
    values.update(overrides)
    return OperatorSafetySnapshot(**values)


def test_expiry_thresholds_escalate_by_minutes() -> None:
    service = OperatorSafetyService()

    info_eval = service.evaluate(snapshot(end_date=instant() + timedelta(minutes=119)))
    warning_eval = service.evaluate(snapshot(end_date=instant() + timedelta(minutes=59)))
    critical_eval = service.evaluate(snapshot(end_date=instant() + timedelta(minutes=14)))

    assert {alert.code for alert in info_eval.alerts} == {"EXPIRY_INFO"}
    assert info_eval.alerts[0].severity == AlertSeverity.INFO
    assert info_eval.new_order_status == NewOrderBlockState.ALLOWED

    assert {alert.code for alert in warning_eval.alerts} == {"EXPIRY_WARNING"}
    assert warning_eval.alerts[0].severity == AlertSeverity.WARNING
    assert warning_eval.new_order_status == NewOrderBlockState.ALLOWED

    assert {alert.code for alert in critical_eval.alerts} == {"EXPIRY_CRITICAL"}
    assert critical_eval.alerts[0].severity == AlertSeverity.CRITICAL
    assert critical_eval.new_order_status == NewOrderBlockState.PARTIALLY_BLOCKED


def test_liquidity_thresholds_respect_ticks_depth_activity_and_gap_fill() -> None:
    service = OperatorSafetyService()

    warning_eval = service.evaluate(
        snapshot(
            best_bid=Decimal("0.46"),
            best_ask=Decimal("0.50"),
            top_of_book_depth_usdc=Decimal("1.5"),
            last_trade_at=instant() - timedelta(minutes=6),
            gap_fill_events_per_minute=Decimal("1"),
            ask_depth_usdc=None,
        )
    )
    critical_eval = service.evaluate(
        snapshot(
            best_bid=Decimal("0.40"),
            best_ask=Decimal("0.46"),
            top_of_book_depth_usdc=Decimal("0.5"),
            last_trade_at=instant() - timedelta(minutes=16),
            gap_fill_events_per_minute=Decimal("4"),
            bid_depth_usdc=Decimal("20"),
            ask_depth_usdc=Decimal("1"),
        )
    )

    assert {
        "LIQUIDITY_SPREAD_WARNING",
        "LIQUIDITY_DEPTH_WARNING",
        "ACTIVITY_WARNING",
        "GAP_FILL_WARNING",
        "BOOK_WARNING",
    }.issubset({alert.code for alert in warning_eval.alerts})
    assert warning_eval.new_order_status == NewOrderBlockState.ALLOWED

    assert {
        "LIQUIDITY_SPREAD_CRITICAL",
        "LIQUIDITY_DEPTH_CRITICAL",
        "ACTIVITY_CRITICAL",
        "GAP_FILL_CRITICAL",
        "BOOK_CRITICAL",
    }.issubset({alert.code for alert in critical_eval.alerts})
    assert critical_eval.new_order_status == NewOrderBlockState.PARTIALLY_BLOCKED


def test_critical_expiry_blocks_only_increasing_exposure() -> None:
    service = OperatorSafetyService()
    evaluation = service.evaluate(
        snapshot(end_date=instant() + timedelta(minutes=10))
    )

    increase = service.gate_action(evaluation, OrderAction.INCREASE_EXPOSURE)
    reduce = service.gate_action(evaluation, OrderAction.REDUCE)
    close = service.gate_action(evaluation, OrderAction.CLOSE)
    risk_release = service.gate_action(evaluation, OrderAction.RISK_RELEASE)

    assert increase.allowed is False
    assert increase.block_state == NewOrderBlockState.PARTIALLY_BLOCKED
    assert "EXPIRY_CRITICAL" in increase.reasons
    assert reduce.allowed is True
    assert close.allowed is True
    assert risk_release.allowed is True


def test_mode_preflight_reports_blockers_before_switch() -> None:
    service = OperatorSafetyService()
    degraded_connections = healthy_connections()
    degraded_connections[0] = ConnectionState(
        component=ConnectionComponent.DB,
        status=ConnectionStatus.DOWN,
        updated_at=instant(),
    )
    degraded_connections[1] = ConnectionState(
        component=ConnectionComponent.MARKET_DATA_WS,
        status=ConnectionStatus.DOWN,
        updated_at=instant(),
    )
    evaluation = service.evaluate(snapshot(connections=degraded_connections))

    preflight = service.preflight(
        current_mode=GlobalMode.REPLAY,
        target_mode=GlobalMode.PAPER,
        connections=degraded_connections,
        evaluation=evaluation,
    )

    assert preflight.allowed is False
    assert preflight.requires_confirmation is True
    assert any("DB is down" in blocker for blocker in preflight.blockers)
    assert any("MARKET_DATA_WS is down" in blocker for blocker in preflight.blockers)
    assert preflight.target_mode == GlobalMode.PAPER
