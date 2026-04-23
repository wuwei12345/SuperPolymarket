from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from polymarket_quant.domain.strategy import (
    StrategyContextSnapshot,
    StrategyEvent,
    StrategyEventType,
    StrategySignal,
)
from polymarket_quant.strategy.base import BaseStrategy


class ScheduledBootstrapStrategy(BaseStrategy):
    """Minimal sample strategy for scheduled paper runs."""

    def __init__(self, target_exposure: Decimal | str = Decimal("0.02")) -> None:
        self.target_exposure = Decimal(str(target_exposure))
        self._emitted_tokens: set[str] = set()

    def on_init(self, ctx: StrategyContextSnapshot) -> list[StrategySignal]:
        self._emitted_tokens.clear()
        return []

    def on_event(
        self, event: StrategyEvent, ctx: StrategyContextSnapshot
    ) -> list[StrategySignal]:
        if event.event_type != StrategyEventType.MARKET or not event.token_id:
            return []
        if event.token_id in self._emitted_tokens:
            return []
        market_data = ctx.market_data.get("by_token", {}).get(event.token_id, {})
        if not market_data.get("active", True) or not market_data.get(
            "accepting_orders", True
        ):
            return []
        self._emitted_tokens.add(event.token_id)
        return [
            StrategySignal(
                token_id=event.token_id,
                target_exposure=self.target_exposure,
                ts=event.ts,
                reason_code="scheduled_bootstrap",
                confidence=Decimal("0.60"),
            )
        ]


class StressProfile(StrEnum):
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


@dataclass(frozen=True)
class StressStage:
    target_exposure: Decimal
    reason_code: str


@dataclass(frozen=True)
class StressProfileConfig:
    profile: StressProfile
    stages: tuple[StressStage, ...]
    stage_interval_seconds: int
    event_trigger_count: int
    max_active_tokens: int
    confidence: Decimal


@dataclass
class TokenCycleState:
    stage_index: int = -1
    last_signal_ts: datetime | None = None
    current_target_exposure: Decimal = Decimal("0")
    events_since_signal: int = 0
    cycle_complete: bool = False
    last_market_data: dict[str, object] | None = None


PROFILE_CONFIGS: dict[StressProfile, StressProfileConfig] = {
    StressProfile.LIGHT: StressProfileConfig(
        profile=StressProfile.LIGHT,
        stages=(
            StressStage(Decimal("0.05"), "stress_light_enter"),
            StressStage(Decimal("0.08"), "stress_light_add"),
            StressStage(Decimal("0.10"), "stress_light_cap"),
            StressStage(Decimal("0.00"), "stress_light_exit"),
        ),
        stage_interval_seconds=30,
        event_trigger_count=3,
        max_active_tokens=10,
        confidence=Decimal("0.65"),
    ),
    StressProfile.MEDIUM: StressProfileConfig(
        profile=StressProfile.MEDIUM,
        stages=(
            StressStage(Decimal("0.05"), "bootstrap_enter"),
            StressStage(Decimal("0.10"), "bootstrap_add"),
            StressStage(Decimal("0.03"), "bootstrap_reduce"),
            StressStage(Decimal("0.00"), "bootstrap_exit"),
        ),
        stage_interval_seconds=20,
        event_trigger_count=2,
        max_active_tokens=10,
        confidence=Decimal("0.70"),
    ),
    StressProfile.HEAVY: StressProfileConfig(
        profile=StressProfile.HEAVY,
        stages=(
            StressStage(Decimal("0.03"), "stress_heavy_enter"),
            StressStage(Decimal("0.12"), "stress_heavy_add_1"),
            StressStage(Decimal("0.06"), "stress_heavy_reduce"),
            StressStage(Decimal("0.15"), "stress_heavy_add_2"),
            StressStage(Decimal("0.00"), "stress_heavy_exit"),
        ),
        stage_interval_seconds=10,
        event_trigger_count=1,
        max_active_tokens=20,
        confidence=Decimal("0.75"),
    ),
}


class ScheduledBootstrapStressStrategy(BaseStrategy):
    """Configurable staged stress strategy for paper execution and reporting validation."""

    def __init__(
        self,
        profile: StressProfile | str = StressProfile.MEDIUM,
        *,
        max_active_tokens: int | None = None,
        stage_interval_seconds: int | None = None,
        event_trigger_count: int | None = None,
    ) -> None:
        self.default_profile = StressProfile(str(profile))
        self.max_active_tokens_override = max_active_tokens
        self.stage_interval_override = stage_interval_seconds
        self.event_trigger_override = event_trigger_count
        self.profile_config = PROFILE_CONFIGS[self.default_profile]
        self._token_states: dict[str, TokenCycleState] = {}

    def on_init(self, ctx: StrategyContextSnapshot) -> list[StrategySignal]:
        self._token_states.clear()
        self.profile_config = self._resolve_profile_config(ctx)
        return []

    def on_event(
        self, event: StrategyEvent, ctx: StrategyContextSnapshot
    ) -> list[StrategySignal]:
        if event.event_type != StrategyEventType.MARKET or not event.token_id:
            return []
        token_id = event.token_id
        market_data = self._market_data(event, ctx)
        state = self._token_states.setdefault(token_id, TokenCycleState())
        state.last_market_data = market_data
        state.events_since_signal += 1
        return self._advance_if_due(token_id, event.ts, market_data)

    def on_clock(
        self, ts: datetime, ctx: StrategyContextSnapshot
    ) -> list[StrategySignal]:
        signals: list[StrategySignal] = []
        for token_id, state in self._token_states.items():
            if state.cycle_complete or state.last_market_data is None:
                continue
            signals.extend(self._advance_if_due(token_id, ts, state.last_market_data))
        return signals

    def _advance_if_due(
        self,
        token_id: str,
        ts: datetime,
        market_data: dict[str, object],
    ) -> list[StrategySignal]:
        state = self._token_states[token_id]
        next_stage_index = state.stage_index + 1
        if next_stage_index >= len(self.profile_config.stages):
            state.cycle_complete = True
            return []
        if state.stage_index < 0:
            if not self._can_start_new_cycle(token_id, market_data):
                return []
        elif not self._ready_for_next_stage(state, ts):
            return []

        next_stage = self.profile_config.stages[next_stage_index]
        if self._blocks_increase(next_stage, state, market_data):
            return []

        state.stage_index = next_stage_index
        state.current_target_exposure = next_stage.target_exposure
        state.last_signal_ts = ts
        state.events_since_signal = 0
        if next_stage.target_exposure == Decimal("0"):
            state.cycle_complete = True
        return [
            StrategySignal(
                token_id=token_id,
                target_exposure=next_stage.target_exposure,
                ts=ts,
                reason_code=next_stage.reason_code,
                confidence=self.profile_config.confidence,
            )
        ]

    def _can_start_new_cycle(
        self,
        token_id: str,
        market_data: dict[str, object],
    ) -> bool:
        if not market_data.get("active", True) or not market_data.get(
            "accepting_orders", True
        ):
            return False
        if self._has_open_exposure_block(market_data):
            return False
        active_cycles = sum(
            1
            for existing_token, state in self._token_states.items()
            if existing_token != token_id
            and state.stage_index >= 0
            and not state.cycle_complete
        )
        return active_cycles < self.profile_config.max_active_tokens

    def _ready_for_next_stage(self, state: TokenCycleState, ts: datetime) -> bool:
        if state.last_signal_ts is None:
            return True
        elapsed = (ts - state.last_signal_ts).total_seconds()
        return (
            elapsed >= self.profile_config.stage_interval_seconds
            or state.events_since_signal >= self.profile_config.event_trigger_count
        )

    def _blocks_increase(
        self,
        next_stage: StressStage,
        state: TokenCycleState,
        market_data: dict[str, object],
    ) -> bool:
        is_increase = next_stage.target_exposure > state.current_target_exposure
        if not is_increase:
            return False
        return self._has_open_exposure_block(market_data)

    def _has_open_exposure_block(self, market_data: dict[str, object]) -> bool:
        if not market_data.get("active", True) or not market_data.get(
            "accepting_orders", True
        ):
            return True
        block_flags = (
            "expiry_critical",
            "liquidity_critical",
            "new_order_blocked",
        )
        if any(bool(market_data.get(flag)) for flag in block_flags):
            return True
        return str(market_data.get("new_order_status", "allowed")) in {
            "partially_blocked",
            "fully_blocked",
        }

    def _market_data(
        self,
        event: StrategyEvent,
        ctx: StrategyContextSnapshot,
    ) -> dict[str, object]:
        event_market_data = event.payload.get("by_token", {}).get(event.token_id or "", {})
        if isinstance(event_market_data, dict):
            return dict(event_market_data)
        ctx_market_data = ctx.market_data.get("by_token", {}).get(event.token_id or "", {})
        if isinstance(ctx_market_data, dict):
            return dict(ctx_market_data)
        return {}

    def _resolve_profile_config(
        self, ctx: StrategyContextSnapshot
    ) -> StressProfileConfig:
        strategy_config = ctx.run_config.strategy
        configured_profile = strategy_config.get("stress_profile", self.default_profile)
        profile = StressProfile(str(configured_profile))
        base_config = PROFILE_CONFIGS[profile]
        max_active_tokens = int(
            strategy_config.get(
                "stress_max_active_tokens",
                self.max_active_tokens_override
                if self.max_active_tokens_override is not None
                else base_config.max_active_tokens,
            )
        )
        stage_interval_seconds = int(
            strategy_config.get(
                "stress_stage_interval_seconds",
                self.stage_interval_override
                if self.stage_interval_override is not None
                else base_config.stage_interval_seconds,
            )
        )
        event_trigger_count = int(
            strategy_config.get(
                "stress_event_trigger_count",
                self.event_trigger_override
                if self.event_trigger_override is not None
                else base_config.event_trigger_count,
            )
        )
        return StressProfileConfig(
            profile=profile,
            stages=base_config.stages,
            stage_interval_seconds=stage_interval_seconds,
            event_trigger_count=event_trigger_count,
            max_active_tokens=max_active_tokens,
            confidence=base_config.confidence,
        )
