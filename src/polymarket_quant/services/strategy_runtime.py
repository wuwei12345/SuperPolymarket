from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from polymarket_quant.domain.strategy import (
    ResolvedRunConfig,
    StrategyContextSnapshot,
    StrategyEvent,
    StrategyEventType,
    StrategySignal,
)
from polymarket_quant.strategy.base import BaseStrategy


@dataclass
class RuntimeState:
    market_data: dict[str, Any] = field(default_factory=dict)
    features: dict[str, Any] = field(default_factory=dict)
    portfolio: dict[str, Any] = field(
        default_factory=lambda: {"positions": {}, "cash": None, "open_orders": []}
    )
    recent_fills: list[dict[str, Any]] = field(default_factory=list)
    recent_risk_decisions: list[dict[str, Any]] = field(default_factory=list)
    emitted_signals: list[StrategySignal] = field(default_factory=list)


class StrategyRuntime:
    def __init__(
        self,
        strategy: BaseStrategy,
        run_config: ResolvedRunConfig,
        time_window: dict[str, Any] | None = None,
        initial_state: RuntimeState | None = None,
    ) -> None:
        self.strategy = strategy
        self.run_config = run_config
        self.time_window = time_window or {}
        self.state = initial_state or RuntimeState()

    def build_context(self, timestamp: datetime) -> StrategyContextSnapshot:
        return StrategyContextSnapshot(
            timestamp=timestamp,
            run_mode=self.run_config.mode,
            market_data=dict(self.state.market_data),
            features=dict(self.state.features),
            portfolio={
                "positions": dict(self.state.portfolio.get("positions", {})),
                "cash": self.state.portfolio.get("cash"),
                "open_orders": list(self.state.portfolio.get("open_orders", [])),
            },
            recent_fills=list(self.state.recent_fills),
            recent_risk_decisions=list(self.state.recent_risk_decisions),
            run_config=self.run_config,
            time_window=dict(self.time_window),
        )

    def on_init(self, timestamp: datetime) -> list[StrategySignal]:
        return self._record_signals(self.strategy.on_init(self.build_context(timestamp)))

    def on_event(self, event: StrategyEvent) -> list[StrategySignal]:
        self._apply_event_feedback(event)
        return self._record_signals(
            self.strategy.on_event(event, self.build_context(event.ts))
        )

    def on_clock(self, timestamp: datetime) -> list[StrategySignal]:
        return self._record_signals(
            self.strategy.on_clock(timestamp, self.build_context(timestamp))
        )

    def on_finish(self, timestamp: datetime) -> list[StrategySignal]:
        return self._record_signals(
            self.strategy.on_finish(self.build_context(timestamp))
        )

    def update_features(self, features: dict[str, Any]) -> None:
        self.state.features.update(features)

    def update_portfolio(
        self,
        *,
        positions: dict[str, Any] | None = None,
        cash: Any | None = None,
        open_orders: list[dict[str, Any]] | None = None,
    ) -> None:
        if positions is not None:
            self.state.portfolio["positions"] = dict(positions)
        if cash is not None:
            self.state.portfolio["cash"] = cash
        if open_orders is not None:
            self.state.portfolio["open_orders"] = list(open_orders)

    def _apply_event_feedback(self, event: StrategyEvent) -> None:
        if event.event_type == StrategyEventType.MARKET:
            self.state.market_data.update(
                {
                    "token_id": event.token_id,
                    "condition_id": event.condition_id,
                    "source": event.source,
                    "event_ts": event.ts.isoformat(),
                    **event.payload,
                }
            )
            feature_snapshot = event.payload.get("features")
            if isinstance(feature_snapshot, dict):
                self.update_features(feature_snapshot)
            return

        if event.event_type == StrategyEventType.EXECUTION:
            fill = _extract_mapping(event.payload, "fill")
            if fill is not None:
                self.state.recent_fills.append(fill)
            positions = event.payload.get("positions")
            if isinstance(positions, dict):
                self.state.portfolio["positions"] = dict(positions)
            if "cash" in event.payload:
                self.state.portfolio["cash"] = event.payload["cash"]
            open_orders = event.payload.get("open_orders")
            if isinstance(open_orders, list):
                self.state.portfolio["open_orders"] = list(open_orders)
            return

        if event.event_type == StrategyEventType.RISK:
            decision = _extract_mapping(event.payload, "risk_decision")
            if decision is not None:
                self.state.recent_risk_decisions.append(decision)

    def _record_signals(self, signals: list[StrategySignal]) -> list[StrategySignal]:
        self.state.emitted_signals.extend(signals)
        return signals


def _extract_mapping(payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = payload.get(key)
    if isinstance(value, dict):
        return dict(value)
    return None
