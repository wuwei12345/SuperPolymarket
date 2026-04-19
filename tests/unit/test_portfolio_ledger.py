from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from polymarket_quant.domain.market_data import BestBidAsk, LastTrade
from polymarket_quant.domain.simulation import (
    LiquidityRole,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionState,
    SimulatedFill,
    SimulatedOrder,
    TimeInForce,
)
from polymarket_quant.services.portfolio_ledger import (
    BEST_BID,
    FEE,
    FILL_NOTIONAL,
    LAST_TRADE_FALLBACK,
    ConservativeMarkPolicy,
    PolymarketFeePolicy,
    PortfolioLedgerService,
    apply_position_change,
    value_position,
)


class RecordingStore:
    def __init__(self) -> None:
        self.cash_entries = []
        self.position_entries = []

    def insert_cash_entry(self, entry: object) -> None:
        self.cash_entries.append(entry)

    def insert_position_entry(self, entry: object) -> None:
        self.position_entries.append(entry)


def instant() -> datetime:
    return datetime(2026, 4, 19, 8, 0, tzinfo=timezone.utc)


def order(**overrides: object) -> SimulatedOrder:
    values = {
        "client_order_id": "order-1",
        "strategy_id": "strategy-a",
        "token_id": "token-yes",
        "condition_id": "0xcondition",
        "side": OrderSide.BUY,
        "order_type": OrderType.LIMIT,
        "price": Decimal("0.50"),
        "size": Decimal("10"),
        "remaining_size": Decimal("10"),
        "status": OrderStatus.OPEN,
        "time_in_force": TimeInForce.GTC,
        "created_at": instant(),
        "updated_at": instant(),
    }
    values.update(overrides)
    return SimulatedOrder(**values)


def fill(**overrides: object) -> SimulatedFill:
    values = {
        "fill_id": "fill-1",
        "client_order_id": "order-1",
        "strategy_id": "strategy-a",
        "token_id": "token-yes",
        "condition_id": "0xcondition",
        "side": OrderSide.BUY,
        "price": Decimal("0.40"),
        "size": Decimal("5"),
        "fee": Decimal("0"),
        "liquidity_role": LiquidityRole.TAKER,
        "created_at": instant(),
    }
    values.update(overrides)
    return SimulatedFill(**values)


def position(**overrides: object) -> PositionState:
    values = {
        "strategy_id": "strategy-a",
        "token_id": "token-yes",
        "condition_id": "0xcondition",
        "quantity": Decimal("10"),
        "average_cost": Decimal("0.40"),
        "realized_pnl": Decimal("0"),
        "fees_paid": Decimal("0"),
    }
    values.update(overrides)
    return PositionState(**values)


def bbo(**overrides: object) -> BestBidAsk:
    values = {
        "token_id": "token-yes",
        "condition_id": "0xcondition",
        "best_bid": Decimal("0.42"),
        "best_ask": Decimal("0.44"),
        "spread": Decimal("0.02"),
        "midpoint": Decimal("0.43"),
    }
    values.update(overrides)
    return BestBidAsk(**values)


def test_buy_fill_debits_cash_and_adds_position() -> None:
    result = PortfolioLedgerService().apply_fill(fill(), order())

    assert result.cash_entry.reason == FILL_NOTIONAL
    assert result.cash_entry.delta == Decimal("-2.00")
    assert result.position_entry.delta == Decimal("5")


def test_sell_fill_credits_cash_and_reduces_position() -> None:
    sell_order = order(side=OrderSide.SELL)
    sell_fill = fill(side=OrderSide.SELL, price=Decimal("0.60"), size=Decimal("4"))

    result = PortfolioLedgerService().apply_fill(sell_fill, sell_order)

    assert result.cash_entry.delta == Decimal("2.40")
    assert result.position_entry.delta == Decimal("-4")


def test_fee_is_recorded_as_separate_cash_entry() -> None:
    store = RecordingStore()
    result = PortfolioLedgerService(store=store).apply_fill(
        fill(fee=Decimal("0.10")), order()
    )

    assert result.fee_entry is not None
    assert result.fee_entry.reason == FEE
    assert result.fee_entry.delta == Decimal("-0.10")
    assert sum(entry.delta for entry in store.cash_entries) == Decimal("-2.10")


def test_taker_fee_uses_polymarket_fee_formula() -> None:
    policy = PolymarketFeePolicy(fee_rate=Decimal("0.02"))

    assert policy.calculate_fee(
        Decimal("0.40"), Decimal("5"), LiquidityRole.TAKER
    ) == Decimal("0.02400")
    assert policy.calculate_fee(
        Decimal("0.40"), Decimal("5"), LiquidityRole.MAKER
    ) == Decimal("0")


def test_conservative_mark_uses_best_bid_for_long_position() -> None:
    mark_price, reason = ConservativeMarkPolicy().mark_long_token(bbo())

    assert mark_price == Decimal("0.42")
    assert reason == BEST_BID


def test_conservative_mark_falls_back_to_last_trade_when_bid_missing() -> None:
    last_trade = LastTrade(token_id="token-yes", price=Decimal("0.41"))

    mark_price, reason = ConservativeMarkPolicy().mark_long_token(
        bbo(best_bid=None), last_trade
    )

    assert mark_price == Decimal("0.41")
    assert reason == LAST_TRADE_FALLBACK


def test_rewards_are_not_included_in_core_pnl() -> None:
    snapshot = value_position(position(), bbo(best_bid=Decimal("0.45")))

    assert snapshot.reward_pnl == Decimal("0")
    assert snapshot.core_pnl == snapshot.total_pnl


def test_sell_fill_realizes_pnl_against_average_cost() -> None:
    updated = apply_position_change(
        position(quantity=Decimal("10"), average_cost=Decimal("0.40")),
        fill(side=OrderSide.SELL, price=Decimal("0.55"), size=Decimal("4")),
        order(side=OrderSide.SELL),
    )

    assert updated.quantity == Decimal("6")
    assert updated.average_cost == Decimal("0.40")
    assert updated.realized_pnl == Decimal("0.60")


def test_unrealized_pnl_remains_separate_from_realized_pnl() -> None:
    snapshot = value_position(
        position(
            quantity=Decimal("10"),
            average_cost=Decimal("0.40"),
            realized_pnl=Decimal("1.00"),
        ),
        bbo(best_bid=Decimal("0.45")),
    )

    assert snapshot.unrealized_pnl == Decimal("0.50")
    assert snapshot.realized_pnl == Decimal("1.00")
    assert snapshot.core_pnl == Decimal("1.50")
