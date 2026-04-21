from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from polymarket_quant.domain.market_data import BookLevel, BookSnapshot
from polymarket_quant.domain.strategy import (
    ResolvedRunConfig,
    RunMode,
    StrategyEvent,
    StrategyEventType,
    StrategySignal,
)
from polymarket_quant.services.order_risk import MarketConstraints, RiskLimits
from polymarket_quant.services.paper_exchange import PaperExchangeService
from polymarket_quant.services.realtime_strategy_runner import RealtimeStrategyRunner
from polymarket_quant.services.signal_execution import SignalExecutionService
from polymarket_quant.services.strategy_runtime import StrategyRuntime
from polymarket_quant.services.fill_engine import FillEngineConfig
from polymarket_quant.strategy.base import BaseStrategy


class EventDrivenSignalStrategy(BaseStrategy):
    def __init__(self, signal: StrategySignal) -> None:
        self.signal = signal

    def on_event(self, event: StrategyEvent, ctx: object) -> list[StrategySignal]:
        if event.event_type == StrategyEventType.MARKET:
            return [self.signal]
        return []


def instant() -> datetime:
    return datetime(2026, 4, 21, 10, 0, tzinfo=timezone.utc)


def run_config() -> ResolvedRunConfig:
    return ResolvedRunConfig(
        strategy={"name": "spread_capture", "version": "0.4.0"},
        universe={"selector": "top_n"},
        sizing={"target_exposure_mode": "fraction_of_equity"},
        execution={"time_in_force": "GTC", "post_only": False},
        risk={"profile": "paper"},
        data_sources={"market": "clob"},
        mode=RunMode.REALTIME_PAPER,
        realtime={"feed": "test"},
    )


def market_event() -> StrategyEvent:
    return StrategyEvent(
        event_type=StrategyEventType.MARKET,
        ts=instant(),
        token_id="token-yes",
        condition_id="0xcondition",
        source="clob_ws",
        payload={
            "by_token": {
                "token-yes": {
                    "token_id": "token-yes",
                    "condition_id": "0xcondition",
                    "best_bid": Decimal("0.44"),
                    "best_ask": Decimal("0.46"),
                    "midpoint": Decimal("0.45"),
                    "last_trade_price": Decimal("0.45"),
                }
            }
        },
    )


def signal(**overrides: object) -> StrategySignal:
    values = {
        "token_id": "token-yes",
        "target_exposure": Decimal("0.50"),
        "ts": instant(),
        "reason_code": "mean_reversion",
    }
    values.update(overrides)
    return StrategySignal(**values)


def constraints() -> MarketConstraints:
    return MarketConstraints(
        token_id="token-yes",
        condition_id="0xcondition",
        tick_size=Decimal("0.01"),
        min_order_size=Decimal("1"),
        best_bid=Decimal("0.44"),
        best_ask=Decimal("0.46"),
        spread=Decimal("0.02"),
    )


def limits() -> RiskLimits:
    return RiskLimits(
        cash_available=Decimal("100"),
        token_position=Decimal("100"),
        max_single_order_notional=Decimal("100"),
        max_market_position=Decimal("100"),
        max_token_position=Decimal("100"),
    )


def snapshot() -> BookSnapshot:
    return BookSnapshot(
        token_id="token-yes",
        condition_id="0xcondition",
        source_ts=instant(),
        received_at=instant(),
        bids=[BookLevel(side="BUY", price=Decimal("0.44"), size=Decimal("10"))],
        asks=[BookLevel(side="SELL", price=Decimal("0.46"), size=Decimal("10"))],
        last_trade_price=Decimal("0.45"),
    )


def runtime_for(strategy: BaseStrategy) -> StrategyRuntime:
    runtime = StrategyRuntime(strategy, run_config())
    runtime.update_portfolio(
        positions={"token-yes": {"quantity": Decimal("20")}},
        cash=Decimal("100"),
        open_orders=[],
    )
    runtime.on_event(market_event())
    return runtime


def test_target_exposure_signal_translates_into_order_intent_delta() -> None:
    runtime = runtime_for(EventDrivenSignalStrategy(signal()))
    context = runtime.build_context(instant())

    intents = SignalExecutionService(strategy_id="strategy-a").translate_signal(
        signal(), context
    )

    assert len(intents) == 1
    assert intents[0].side.value == "BUY"
    assert intents[0].price == Decimal("0.46")
    assert intents[0].size == Decimal("101.1111111111111111111111111")


def test_target_position_fallback_is_supported() -> None:
    runtime = runtime_for(
        EventDrivenSignalStrategy(
            signal(target_exposure=None, target_position=Decimal("12"))
        )
    )
    context = runtime.build_context(instant())

    intents = SignalExecutionService(strategy_id="strategy-a").translate_signal(
        signal(target_exposure=None, target_position=Decimal("12")), context
    )

    assert len(intents) == 1
    assert intents[0].side.value == "SELL"
    assert intents[0].size == Decimal("8")
    assert intents[0].price == Decimal("0.44")


def test_realtime_runner_routes_orders_through_paper_exchange() -> None:
    strategy = EventDrivenSignalStrategy(
        signal(target_exposure=None, target_position=Decimal("25"))
    )
    runtime = StrategyRuntime(strategy, run_config())
    runtime.update_portfolio(
        positions={"token-yes": {"quantity": Decimal("20")}},
        cash=Decimal("100"),
        open_orders=[],
    )

    runner = RealtimeStrategyRunner(
        runtime=runtime,
        signal_execution=SignalExecutionService(strategy_id="strategy-a"),
        paper_exchange=PaperExchangeService(
            fill_config=FillEngineConfig(submit_latency_ms=0, cancel_latency_ms=0)
        ),
        constraints_provider=lambda _signal: constraints(),
        limits_provider=lambda _signal: limits(),
        snapshot_provider=lambda _signal: snapshot(),
    )

    result = runner.on_event(market_event())

    assert len(result.signals) == 1
    assert len(result.order_intents) == 1
    assert len(result.paper_results) == 1
    assert result.order_intents[0].client_order_id == result.paper_results[0].order.client_order_id
    assert result.paper_results[0].risk_decision is not None


def test_execution_feedback_updates_runtime_context() -> None:
    strategy = EventDrivenSignalStrategy(
        signal(target_exposure=None, target_position=Decimal("25"))
    )
    runtime = StrategyRuntime(strategy, run_config())
    runtime.update_portfolio(
        positions={"token-yes": {"quantity": Decimal("20")}},
        cash=Decimal("100"),
        open_orders=[],
    )

    runner = RealtimeStrategyRunner(
        runtime=runtime,
        signal_execution=SignalExecutionService(strategy_id="strategy-a"),
        paper_exchange=PaperExchangeService(
            fill_config=FillEngineConfig(submit_latency_ms=0, cancel_latency_ms=0)
        ),
        constraints_provider=lambda _signal: constraints(),
        limits_provider=lambda _signal: limits(),
        snapshot_provider=lambda _signal: snapshot(),
    )

    runner.on_event(market_event())
    context = runtime.build_context(instant())

    assert context.recent_risk_decisions
    assert context.recent_fills
    assert context.portfolio["positions"]["token-yes"]["quantity"] == Decimal("25")
    assert context.portfolio["cash"] == Decimal("97.70")
