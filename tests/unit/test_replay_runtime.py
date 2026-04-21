from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from polymarket_quant.domain.strategy import (
    ResolvedRunConfig,
    RunMode,
    StrategyEvent,
    StrategyEventType,
    StrategySignal,
)
from polymarket_quant.services.replay_runtime import ReplayRuntime
from polymarket_quant.services.strategy_runtime import StrategyRuntime
from polymarket_quant.strategy.base import BaseStrategy


def instant() -> datetime:
    return datetime(2026, 4, 21, 8, 0, tzinfo=timezone.utc)


def run_config(**overrides: object) -> ResolvedRunConfig:
    values = {
        "strategy": {"name": "recorder"},
        "universe": {"selector": "top_n", "top_n": 25},
        "sizing": {"mode": "exposure"},
        "execution": {"style": "limit"},
        "risk": {"max_token_position": "100"},
        "data_sources": {"market_data": "postgres"},
        "mode": RunMode.REPLAY,
        "replay": {"window_start": "2026-04-20T00:00:00Z"},
        "realtime": {},
        "step_interval": "1m",
    }
    values.update(overrides)
    return ResolvedRunConfig(**values)


class RecordingStrategy(BaseStrategy):
    def __init__(self) -> None:
        self.clock_observations: list[tuple[datetime, dict[str, object]]] = []
        self.init_contexts = []
        self.finish_contexts = []

    def on_init(self, ctx):  # type: ignore[override]
        self.init_contexts.append(ctx)
        return []

    def on_clock(self, ts, ctx):  # type: ignore[override]
        self.clock_observations.append((ts, dict(ctx.market_data)))
        signal = None
        if ctx.market_data.get("token_id") is not None:
            signal = StrategySignal(
                token_id=str(ctx.market_data["token_id"]),
                target_exposure=Decimal("0.10"),
                ts=ts,
                reason_code="clock_tick",
            )
        return [] if signal is None else [signal]

    def on_finish(self, ctx):  # type: ignore[override]
        self.finish_contexts.append(ctx)
        return []


def market_event(ts: datetime, **payload: object) -> StrategyEvent:
    return StrategyEvent(
        event_type=StrategyEventType.MARKET,
        ts=ts,
        token_id="token-yes",
        condition_id="0xcondition",
        source="normalized",
        payload=dict(payload),
    )


def execution_event(ts: datetime, **payload: object) -> StrategyEvent:
    return StrategyEvent(
        event_type=StrategyEventType.EXECUTION,
        ts=ts,
        token_id="token-yes",
        source="paper_exchange",
        payload=dict(payload),
    )


def risk_event(ts: datetime, **payload: object) -> StrategyEvent:
    return StrategyEvent(
        event_type=StrategyEventType.RISK,
        ts=ts,
        token_id="token-yes",
        source="risk",
        payload=dict(payload),
    )


def test_runtime_context_includes_market_features_positions_and_risk() -> None:
    runtime = StrategyRuntime(RecordingStrategy(), run_config())
    runtime.update_features({"zscore": 1.8})
    runtime.update_portfolio(positions={"token-yes": "5"}, cash="1000", open_orders=[])
    runtime.on_event(
        execution_event(
            instant(),
            fill={"fill_id": "fill-1", "size": "2"},
            positions={"token-yes": "7"},
            cash="995",
        )
    )
    runtime.on_event(
        risk_event(
            instant(),
            risk_decision={"decision": "WARN", "reason": "PORTFOLIO_EXPOSURE_WARNING"},
        )
    )
    runtime.on_event(
        market_event(
            instant(),
            best_bid="0.44",
            gap_fill=True,
        )
    )

    ctx = runtime.build_context(instant())

    assert ctx.market_data["best_bid"] == "0.44"
    assert ctx.market_data["gap_fill"] is True
    assert ctx.features["zscore"] == 1.8
    assert ctx.portfolio["positions"]["token-yes"] == "7"
    assert ctx.portfolio["cash"] == "995"
    assert ctx.recent_fills[0]["fill_id"] == "fill-1"
    assert ctx.recent_risk_decisions[0]["decision"] == "WARN"


def test_replay_runner_triggers_clock_on_time_boundaries() -> None:
    strategy = RecordingStrategy()
    runtime = StrategyRuntime(strategy, run_config())
    runner = ReplayRuntime(runtime, time_step=timedelta(minutes=1))

    result = runner.run(
        [
            market_event(instant() + timedelta(seconds=10), best_bid="0.40"),
            market_event(instant() + timedelta(minutes=2, seconds=10), best_bid="0.45"),
        ]
    )

    assert result.clock_ticks == [
        instant() + timedelta(minutes=1),
        instant() + timedelta(minutes=2),
    ]
    assert len(result.signals) == 2


def test_replay_runner_does_not_leak_future_rows() -> None:
    strategy = RecordingStrategy()
    runtime = StrategyRuntime(strategy, run_config())
    runner = ReplayRuntime(runtime, time_step=timedelta(minutes=1))

    runner.run(
        [
            market_event(instant() + timedelta(seconds=10), best_bid="0.40"),
            market_event(instant() + timedelta(minutes=1, seconds=10), best_bid="0.80"),
        ]
    )

    first_clock_ts, first_clock_snapshot = strategy.clock_observations[0]
    assert first_clock_ts == instant() + timedelta(minutes=1)
    assert first_clock_snapshot["best_bid"] == "0.40"


def test_gap_fill_marker_survives_into_runtime_context() -> None:
    strategy = RecordingStrategy()
    runtime = StrategyRuntime(strategy, run_config())
    runner = ReplayRuntime(runtime, time_step=timedelta(minutes=1))

    runner.run(
        [
            market_event(
                instant() + timedelta(seconds=5),
                best_bid="0.44",
                gap_fill=True,
            ),
            market_event(
                instant() + timedelta(minutes=1, seconds=5),
                best_bid="0.46",
                gap_fill=False,
            ),
        ]
    )

    _, first_clock_snapshot = strategy.clock_observations[0]
    assert first_clock_snapshot["gap_fill"] is True
