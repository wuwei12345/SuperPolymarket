from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict

from polymarket_quant.domain.simulation import (
    OrderIntent,
    OrderSide,
    TimeInForce,
)
from polymarket_quant.domain.strategy import StrategyContextSnapshot, StrategySignal


class SignalExecutionService(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str

    def translate_signal(
        self, signal: StrategySignal, context: StrategyContextSnapshot
    ) -> list[OrderIntent]:
        target_position = self._resolve_target_position(signal, context)
        current_position = self._current_position(signal.token_id, context)
        delta = target_position - current_position
        if delta == 0:
            return []

        side = OrderSide.BUY if delta > 0 else OrderSide.SELL
        price = self._execution_price(signal.token_id, side, context)
        size = abs(delta)
        execution_config = context.run_config.execution
        created_at = signal.ts
        return [
            OrderIntent(
                client_order_id=self._client_order_id(signal, created_at),
                strategy_id=self.strategy_id,
                token_id=signal.token_id,
                condition_id=self._condition_id(signal.token_id, context),
                side=side,
                price=price,
                size=size,
                time_in_force=TimeInForce(
                    execution_config.get("time_in_force", TimeInForce.GTC)
                ),
                post_only=bool(execution_config.get("post_only", False)),
                expires_at=execution_config.get("expires_at"),
                created_at=created_at,
            )
        ]

    def _resolve_target_position(
        self, signal: StrategySignal, context: StrategyContextSnapshot
    ) -> Decimal:
        if signal.target_position is not None:
            return signal.target_position

        price = self._reference_price(signal.token_id, context)
        if price <= 0:
            raise ValueError("target_exposure requires a positive reference price")
        target_notional = self._target_notional(signal, context)
        return target_notional / price

    def _target_notional(
        self, signal: StrategySignal, context: StrategyContextSnapshot
    ) -> Decimal:
        if signal.target_exposure is None:
            return Decimal("0")

        sizing_config = context.run_config.sizing
        exposure_mode = str(
            sizing_config.get("target_exposure_mode", "fraction_of_equity")
        )
        if exposure_mode == "notional":
            return signal.target_exposure
        if exposure_mode != "fraction_of_equity":
            raise ValueError(f"unsupported exposure mode: {exposure_mode}")

        equity = self._portfolio_equity(context)
        return equity * signal.target_exposure

    def _portfolio_equity(self, context: StrategyContextSnapshot) -> Decimal:
        cash = self._as_decimal(context.portfolio.get("cash"))
        positions = context.portfolio.get("positions", {})
        total_positions = Decimal("0")
        if isinstance(positions, dict):
            for token_id, position in positions.items():
                quantity = self._position_quantity(position)
                total_positions += quantity * self._reference_price(token_id, context)
        return cash + total_positions

    def _current_position(
        self, token_id: str, context: StrategyContextSnapshot
    ) -> Decimal:
        positions = context.portfolio.get("positions", {})
        if not isinstance(positions, dict):
            return Decimal("0")
        position = positions.get(token_id)
        return self._position_quantity(position)

    def _position_quantity(self, position: object) -> Decimal:
        if isinstance(position, dict):
            return self._as_decimal(position.get("quantity"))
        if position is None:
            return Decimal("0")
        return self._as_decimal(position)

    def _execution_price(
        self, token_id: str, side: OrderSide, context: StrategyContextSnapshot
    ) -> Decimal:
        market_data = self._token_market_data(token_id, context)
        if side == OrderSide.BUY:
            candidate = market_data.get("best_ask")
        else:
            candidate = market_data.get("best_bid")
        return self._first_decimal(
            candidate,
            market_data.get("midpoint"),
            market_data.get("last_trade_price"),
            Decimal("0.5"),
        )

    def _reference_price(
        self, token_id: str, context: StrategyContextSnapshot
    ) -> Decimal:
        market_data = self._token_market_data(token_id, context)
        return self._first_decimal(
            market_data.get("midpoint"),
            market_data.get("last_trade_price"),
            market_data.get("best_ask"),
            market_data.get("best_bid"),
            Decimal("0.5"),
        )

    def _condition_id(
        self, token_id: str, context: StrategyContextSnapshot
    ) -> str | None:
        market_data = self._token_market_data(token_id, context)
        condition_id = market_data.get("condition_id")
        if condition_id is None:
            return None
        return str(condition_id)

    def _token_market_data(
        self, token_id: str, context: StrategyContextSnapshot
    ) -> dict[str, object]:
        market_data = context.market_data
        by_token = market_data.get("by_token")
        if isinstance(by_token, dict):
            token_market = by_token.get(token_id)
            if isinstance(token_market, dict):
                return token_market
        return market_data

    def _client_order_id(self, signal: StrategySignal, created_at: datetime) -> str:
        signal_ts = created_at.strftime("%Y%m%d%H%M%S%f")
        suffix = uuid4().hex[:8]
        return f"{self.strategy_id}-{signal.token_id}-{signal_ts}-{suffix}"

    @staticmethod
    def _as_decimal(value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        if value is None:
            return Decimal("0")
        return Decimal(str(value))

    def _first_decimal(self, *candidates: object) -> Decimal:
        for candidate in candidates:
            if candidate is None:
                continue
            value = self._as_decimal(candidate)
            if value > 0:
                return value
        raise ValueError("no positive market price is available")
