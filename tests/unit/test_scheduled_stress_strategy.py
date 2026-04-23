from __future__ import annotations

from datetime import datetime, timedelta, timezone

from polymarket_quant.domain.strategy import (
    ResolvedRunConfig,
    RunMode,
    StrategyContextSnapshot,
    StrategyEvent,
    StrategyEventType,
)
from polymarket_quant.strategy.scheduled import (
    ScheduledBootstrapStrategy,
    ScheduledBootstrapStressStrategy,
)


def instant() -> datetime:
    return datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)


def context(*, strategy_config: dict[str, object] | None = None) -> StrategyContextSnapshot:
    return StrategyContextSnapshot(
        timestamp=instant(),
        run_mode=RunMode.REALTIME_PAPER,
        market_data={},
        features={},
        portfolio={"cash": "1000", "positions": {}, "open_orders": []},
        recent_fills=[],
        recent_risk_decisions=[],
        run_config=ResolvedRunConfig(
            strategy={
                "name": "stress",
                "version": "0.1.0",
                **(strategy_config or {}),
            },
            universe={},
            sizing={},
            execution={},
            risk={},
            data_sources={},
            mode=RunMode.REALTIME_PAPER,
            replay={},
            realtime={},
        ),
        time_window={},
    )


def market_event(
    token_id: str,
    *,
    ts: datetime,
    active: bool = True,
    accepting_orders: bool = True,
    **overrides: object,
) -> StrategyEvent:
    payload = {
        "by_token": {
            token_id: {
                "token_id": token_id,
                "active": active,
                "accepting_orders": accepting_orders,
                **overrides,
            }
        }
    }
    return StrategyEvent(
        event_type=StrategyEventType.MARKET,
        ts=ts,
        token_id=token_id,
        condition_id=f"condition-{token_id}",
        source="test.market",
        payload=payload,
    )


def test_original_bootstrap_strategy_still_emits_single_entry_signal() -> None:
    strategy = ScheduledBootstrapStrategy()
    snapshot = context()
    strategy.on_init(snapshot)

    first = strategy.on_event(market_event("token-1", ts=instant()), snapshot)
    second = strategy.on_event(
        market_event("token-1", ts=instant() + timedelta(seconds=60)),
        snapshot,
    )

    assert len(first) == 1
    assert str(first[0].target_exposure) == "0.02"
    assert second == []


def test_stress_strategy_medium_profile_runs_single_token_full_cycle() -> None:
    strategy = ScheduledBootstrapStressStrategy()
    snapshot = context()
    strategy.on_init(snapshot)

    enter = strategy.on_event(market_event("token-1", ts=instant()), snapshot)
    add = strategy.on_event(
        market_event("token-1", ts=instant() + timedelta(seconds=20)),
        snapshot,
    )
    reduce = strategy.on_event(
        market_event("token-1", ts=instant() + timedelta(seconds=40)),
        snapshot,
    )
    exit_signal = strategy.on_event(
        market_event("token-1", ts=instant() + timedelta(seconds=60)),
        snapshot,
    )
    done = strategy.on_event(
        market_event("token-1", ts=instant() + timedelta(seconds=80)),
        snapshot,
    )

    assert str(enter[0].target_exposure) == "0.05"
    assert enter[0].reason_code == "bootstrap_enter"
    assert str(add[0].target_exposure) == "0.10"
    assert add[0].reason_code == "bootstrap_add"
    assert str(reduce[0].target_exposure) == "0.03"
    assert reduce[0].reason_code == "bootstrap_reduce"
    assert str(exit_signal[0].target_exposure) == "0.00"
    assert exit_signal[0].reason_code == "bootstrap_exit"
    assert done == []


def test_stress_strategy_honors_active_cycle_limit_for_new_tokens() -> None:
    strategy = ScheduledBootstrapStressStrategy(max_active_tokens=2)
    snapshot = context()
    strategy.on_init(snapshot)

    first = strategy.on_event(market_event("token-1", ts=instant()), snapshot)
    second = strategy.on_event(
        market_event("token-2", ts=instant() + timedelta(seconds=1)),
        snapshot,
    )
    blocked = strategy.on_event(
        market_event("token-3", ts=instant() + timedelta(seconds=2)),
        snapshot,
    )

    assert len(first) == 1
    assert len(second) == 1
    assert blocked == []


def test_stress_strategy_blocks_new_opening_but_allows_exit_under_critical_flags() -> None:
    strategy = ScheduledBootstrapStressStrategy(profile="medium")
    snapshot = context()
    strategy.on_init(snapshot)

    enter = strategy.on_event(market_event("token-1", ts=instant()), snapshot)
    add = strategy.on_event(
        market_event(
            "token-1",
            ts=instant() + timedelta(seconds=20),
        ),
        snapshot,
    )
    reduce_signal = strategy.on_event(
        market_event(
            "token-1",
            ts=instant() + timedelta(seconds=40),
            liquidity_critical=True,
            new_order_status="fully_blocked",
        ),
        snapshot,
    )
    blocked_new = strategy.on_event(
        market_event(
            "token-2",
            ts=instant() + timedelta(seconds=41),
            expiry_critical=True,
            new_order_status="fully_blocked",
        ),
        snapshot,
    )

    assert len(enter) == 1
    assert str(add[0].target_exposure) == "0.10"
    assert str(reduce_signal[0].target_exposure) == "0.03"
    assert blocked_new == []


def test_stress_strategy_reads_profile_overrides_from_run_config() -> None:
    strategy = ScheduledBootstrapStressStrategy()
    snapshot = context(
        strategy_config={
            "stress_profile": "heavy",
            "stress_max_active_tokens": 1,
            "stress_stage_interval_seconds": 5,
            "stress_event_trigger_count": 4,
        }
    )
    strategy.on_init(snapshot)

    first = strategy.on_event(market_event("token-1", ts=instant()), snapshot)
    second = strategy.on_event(
        market_event("token-1", ts=instant() + timedelta(seconds=5)),
        snapshot,
    )
    blocked_other = strategy.on_event(
        market_event("token-2", ts=instant() + timedelta(seconds=6)),
        snapshot,
    )

    assert first[0].reason_code == "stress_heavy_enter"
    assert second[0].reason_code == "stress_heavy_add_1"
    assert blocked_other == []
