from __future__ import annotations

from datetime import datetime

from polymarket_quant.domain.strategy import StrategyContextSnapshot, StrategyEvent, StrategySignal


class BaseStrategy:
    """Shared strategy lifecycle contract for replay and realtime paper modes."""

    def on_init(self, ctx: StrategyContextSnapshot) -> list[StrategySignal]:
        """Initialize parameters, universe, run metadata, and local state."""
        return []

    def on_event(
        self, event: StrategyEvent, ctx: StrategyContextSnapshot
    ) -> list[StrategySignal]:
        """Consume market, execution, risk, or system events and update local state."""
        return []

    def on_clock(
        self, ts: datetime, ctx: StrategyContextSnapshot
    ) -> list[StrategySignal]:
        """Emit research-mode fixed-step decisions from the current snapshot and features."""
        return []

    def on_finish(self, ctx: StrategyContextSnapshot) -> list[StrategySignal]:
        """Finalize run-specific debug output and clean up any local resources."""
        return []
