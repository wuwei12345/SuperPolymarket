from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from pydantic import BaseModel, ConfigDict

from polymarket_quant.domain.market_data import BestBidAsk, LastTrade, utc_now
from polymarket_quant.domain.simulation import (
    CashLedgerEntry,
    LiquidityRole,
    OrderSide,
    PositionLedgerEntry,
    PositionState,
    SimulatedFill,
    SimulatedOrder,
    ValuationSnapshot,
)

FILL_NOTIONAL = "FILL_NOTIONAL"
FEE = "FEE"
BEST_BID = "BEST_BID"
LAST_TRADE_FALLBACK = "LAST_TRADE_FALLBACK"
ZERO_FALLBACK = "ZERO_FALLBACK"


class PolymarketFeePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fee_rate: Decimal = Decimal("0")

    def calculate_fee(
        self, price: Decimal, size: Decimal, liquidity_role: LiquidityRole
    ) -> Decimal:
        if liquidity_role == LiquidityRole.MAKER:
            return Decimal("0")
        raw_fee = size * self.fee_rate * price * (Decimal("1") - price)
        return raw_fee.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)


class LedgerUpdateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cash_entry: CashLedgerEntry
    position_entry: PositionLedgerEntry
    fee_entry: CashLedgerEntry | None = None

    @property
    def total_cash_delta(self) -> Decimal:
        fee_delta = self.fee_entry.delta if self.fee_entry is not None else Decimal("0")
        return self.cash_entry.delta + fee_delta


class PortfolioLedgerService:
    def __init__(
        self,
        store: Any | None = None,
        starting_cash: Decimal = Decimal("0"),
        fee_policy: PolymarketFeePolicy | None = None,
    ) -> None:
        self.store = store
        self.starting_cash = starting_cash
        self.fee_policy = fee_policy or PolymarketFeePolicy()

    def apply_fill(
        self, fill: SimulatedFill, order: SimulatedOrder
    ) -> LedgerUpdateResult:
        fee = fill.fee
        if fee == 0:
            fee = self.fee_policy.calculate_fee(
                fill.price, fill.size, fill.liquidity_role
            )
            fill = fill.model_copy(update={"fee": fee})

        notional = fill.price * fill.size
        cash_delta = notional if order.side == OrderSide.SELL else -notional
        position_delta = fill.size if order.side == OrderSide.BUY else -fill.size

        cash_entry = CashLedgerEntry(
            entry_id=f"cash-{fill.fill_id}",
            strategy_id=fill.strategy_id,
            client_order_id=fill.client_order_id,
            fill_id=fill.fill_id,
            delta=cash_delta,
            reason=FILL_NOTIONAL,
            created_at=fill.created_at,
        )
        position_entry = PositionLedgerEntry(
            entry_id=f"position-{fill.fill_id}",
            strategy_id=fill.strategy_id,
            token_id=fill.token_id,
            condition_id=fill.condition_id,
            client_order_id=fill.client_order_id,
            fill_id=fill.fill_id,
            delta=position_delta,
            price=fill.price,
            reason=FILL_NOTIONAL,
            created_at=fill.created_at,
        )
        fee_entry = None
        if fee > 0:
            fee_entry = CashLedgerEntry(
                entry_id=f"fee-{fill.fill_id}",
                strategy_id=fill.strategy_id,
                client_order_id=fill.client_order_id,
                fill_id=fill.fill_id,
                delta=-fee,
                reason=FEE,
                created_at=fill.created_at,
            )

        result = LedgerUpdateResult(
            cash_entry=cash_entry,
            position_entry=position_entry,
            fee_entry=fee_entry,
        )
        if self.store is not None:
            self.store.insert_cash_entry(cash_entry)
            if fee_entry is not None:
                self.store.insert_cash_entry(fee_entry)
            self.store.insert_position_entry(position_entry)
        return result


class ConservativeMarkPolicy:
    def mark_long_token(
        self, bbo: BestBidAsk, last_trade: LastTrade | None = None
    ) -> tuple[Decimal, str]:
        if bbo.best_bid is not None:
            return bbo.best_bid, BEST_BID
        if last_trade is not None:
            return last_trade.price, LAST_TRADE_FALLBACK
        return Decimal("0"), ZERO_FALLBACK


def apply_position_change(
    position: PositionState, fill: SimulatedFill, order: SimulatedOrder
) -> PositionState:
    if order.side == OrderSide.BUY:
        new_quantity = position.quantity + fill.size
        total_cost = position.average_cost * position.quantity + fill.price * fill.size
        average_cost = (
            Decimal("0") if new_quantity == 0 else total_cost / new_quantity
        )
        return position.model_copy(
            update={
                "quantity": new_quantity,
                "average_cost": average_cost,
                "fees_paid": position.fees_paid + fill.fee,
            }
        )

    new_quantity = position.quantity - fill.size
    realized_delta = (fill.price - position.average_cost) * fill.size - fill.fee
    average_cost = Decimal("0") if new_quantity == 0 else position.average_cost
    return position.model_copy(
        update={
            "quantity": new_quantity,
            "average_cost": average_cost,
            "realized_pnl": position.realized_pnl + realized_delta,
            "fees_paid": position.fees_paid + fill.fee,
        }
    )


def value_position(
    position: PositionState,
    bbo: BestBidAsk,
    last_trade: LastTrade | None = None,
) -> ValuationSnapshot:
    mark_price, mark_reason = ConservativeMarkPolicy().mark_long_token(bbo, last_trade)
    unrealized_pnl = (mark_price - position.average_cost) * position.quantity
    core_pnl = position.realized_pnl + unrealized_pnl
    reward_pnl = Decimal("0")
    return ValuationSnapshot(
        strategy_id=position.strategy_id,
        token_id=position.token_id,
        condition_id=position.condition_id,
        quantity=position.quantity,
        average_cost=position.average_cost,
        mark_price=mark_price,
        mark_reason=mark_reason,
        realized_pnl=position.realized_pnl,
        unrealized_pnl=unrealized_pnl,
        core_pnl=core_pnl,
        reward_pnl=reward_pnl,
        total_pnl=core_pnl,
        created_at=utc_now(),
    )
