from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from polymarket_quant.domain.strategy import (
    StrategyContextSnapshot,
    StrategyEvent,
    StrategyEventType,
    StrategySignal,
)
from polymarket_quant.strategy.base import BaseStrategy


@dataclass(frozen=True)
class DefaultProbeConfig:
    risk_level: str
    stake_per_trade: Decimal
    max_positions: int
    min_liquidity: Decimal
    min_volume_24h: Decimal
    confidence: Decimal


class DefaultProbeStrategy(BaseStrategy):
    """Small, conservative default strategy for first-run paper simulations."""

    def __init__(self) -> None:
        self._emitted_tokens: set[str] = set()
        self._config = DefaultProbeConfig(
            risk_level="low",
            stake_per_trade=Decimal("10"),
            max_positions=3,
            min_liquidity=Decimal("1000"),
            min_volume_24h=Decimal("250"),
            confidence=Decimal("0.55"),
        )

    def on_init(self, ctx: StrategyContextSnapshot) -> list[StrategySignal]:
        self._emitted_tokens.clear()
        self._config = self._resolve_config(ctx)
        return []

    def on_event(
        self, event: StrategyEvent, ctx: StrategyContextSnapshot
    ) -> list[StrategySignal]:
        if event.event_type != StrategyEventType.MARKET or not event.token_id:
            return []
        token_id = event.token_id
        if token_id in self._emitted_tokens:
            return []
        market_data = self._market_data(event, ctx)
        if not self._can_probe(token_id, market_data, ctx):
            return []

        self._emitted_tokens.add(token_id)
        return [
            StrategySignal(
                token_id=token_id,
                target_exposure=self._config.stake_per_trade,
                ts=event.ts,
                reason_code="default_probe_enter",
                confidence=self._config.confidence,
            )
        ]

    def _can_probe(
        self,
        token_id: str,
        market_data: dict[str, object],
        ctx: StrategyContextSnapshot,
    ) -> bool:
        if not market_data.get("active", True) or not market_data.get(
            "accepting_orders", True
        ):
            return False
        if self._is_safety_blocked(market_data):
            return False
        if self._active_position_count(ctx) + len(self._emitted_tokens) >= self._config.max_positions:
            return False
        liquidity = _optional_decimal(market_data.get("liquidity"))
        if liquidity is not None and liquidity < self._config.min_liquidity:
            return False
        volume_24h = _optional_decimal(
            market_data.get("volume_24h") or market_data.get("volume24hr")
        )
        if volume_24h is not None and volume_24h < self._config.min_volume_24h:
            return False
        return token_id not in self._held_tokens(ctx)

    @staticmethod
    def _is_safety_blocked(market_data: dict[str, object]) -> bool:
        if any(
            bool(market_data.get(flag))
            for flag in ("expiry_critical", "liquidity_critical", "new_order_blocked")
        ):
            return True
        return str(market_data.get("new_order_status", "allowed")) in {
            "partially_blocked",
            "fully_blocked",
        }

    @staticmethod
    def _active_position_count(ctx: StrategyContextSnapshot) -> int:
        return len(DefaultProbeStrategy._held_tokens(ctx))

    @staticmethod
    def _held_tokens(ctx: StrategyContextSnapshot) -> set[str]:
        positions = ctx.portfolio.get("positions", {})
        if not isinstance(positions, dict):
            return set()
        held = set()
        for token_id, position in positions.items():
            quantity = Decimal("0")
            if isinstance(position, dict):
                quantity = _as_decimal(position.get("quantity"))
            elif position is not None:
                quantity = _as_decimal(position)
            if quantity != 0:
                held.add(str(token_id))
        return held

    @staticmethod
    def _market_data(
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

    @staticmethod
    def _resolve_config(ctx: StrategyContextSnapshot) -> DefaultProbeConfig:
        raw = ctx.run_config.strategy
        risk_level = str(raw.get("risk_level", "low"))
        return DefaultProbeConfig(
            risk_level=risk_level,
            stake_per_trade=_as_decimal(raw.get("stake_per_trade", "10")),
            max_positions=int(raw.get("max_positions", 3)),
            min_liquidity=_as_decimal(raw.get("min_liquidity", "1000")),
            min_volume_24h=_as_decimal(raw.get("min_volume_24h", "250")),
            confidence=_as_decimal(raw.get("confidence", _confidence_for_risk(risk_level))),
        )


def _confidence_for_risk(risk_level: str) -> str:
    return {
        "low": "0.55",
        "medium": "0.65",
        "high": "0.75",
    }.get(risk_level, "0.55")


def _optional_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    return _as_decimal(value)


def _as_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")
