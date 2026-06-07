from __future__ import annotations

from datetime import datetime, timezone

from polymarket_quant.domain.strategy import (
    ResolvedRunConfig,
    RunMode,
    StrategyContextSnapshot,
    StrategyEvent,
    StrategyEventType,
)
from polymarket_quant.strategy.default_probe import DefaultProbeStrategy


def instant() -> datetime:
    return datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)


def context(*, strategy_config: dict[str, object] | None = None, positions: dict[str, object] | None = None) -> StrategyContextSnapshot:
    return StrategyContextSnapshot(
        timestamp=instant(),
        run_mode=RunMode.REALTIME_PAPER,
        market_data={},
        features={},
        portfolio={"cash": "1000", "positions": positions or {}, "open_orders": []},
        recent_fills=[],
        recent_risk_decisions=[],
        run_config=ResolvedRunConfig(
            strategy={
                "name": "default_probe",
                "version": "0.1.0",
                "risk_level": "low",
                "stake_per_trade": "10",
                "max_positions": 2,
                "min_liquidity": "1000",
                "min_volume_24h": "250",
                "confidence": "0.55",
                **(strategy_config or {}),
            },
            universe={},
            sizing={"target_exposure_mode": "notional"},
            execution={},
            risk={},
            data_sources={},
            mode=RunMode.REALTIME_PAPER,
            replay={},
            realtime={},
        ),
        time_window={},
    )


def market_event(token_id: str, **overrides: object) -> StrategyEvent:
    payload = {
        "by_token": {
            token_id: {
                "token_id": token_id,
                "active": True,
                "accepting_orders": True,
                "liquidity": "2000",
                "volume_24h": "500",
                **overrides,
            }
        }
    }
    return StrategyEvent(
        event_type=StrategyEventType.MARKET,
        ts=instant(),
        token_id=token_id,
        condition_id=f"condition-{token_id}",
        source="test.market",
        payload=payload,
    )


def test_default_probe_emits_one_small_notional_signal_per_token() -> None:
    strategy = DefaultProbeStrategy()
    snapshot = context()
    strategy.on_init(snapshot)

    first = strategy.on_event(market_event("token-1"), snapshot)
    duplicate = strategy.on_event(market_event("token-1"), snapshot)

    assert len(first) == 1
    assert first[0].reason_code == "default_probe_enter"
    assert str(first[0].target_exposure) == "10"
    assert str(first[0].confidence) == "0.55"
    assert duplicate == []


def test_default_probe_blocks_bad_markets_and_position_overflow() -> None:
    strategy = DefaultProbeStrategy()
    snapshot = context(strategy_config={"max_positions": 1})
    strategy.on_init(snapshot)

    assert strategy.on_event(market_event("inactive", active=False), snapshot) == []
    assert strategy.on_event(market_event("thin", liquidity="100"), snapshot) == []

    first = strategy.on_event(market_event("token-1"), snapshot)
    second = strategy.on_event(market_event("token-2"), snapshot)

    assert len(first) == 1
    assert second == []


def test_default_probe_respects_existing_portfolio_positions() -> None:
    strategy = DefaultProbeStrategy()
    snapshot = context(
        strategy_config={"max_positions": 1},
        positions={"already-held": {"quantity": "5"}},
    )
    strategy.on_init(snapshot)

    assert strategy.on_event(market_event("token-1"), snapshot) == []
