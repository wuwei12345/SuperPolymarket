from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class MarketDisplayModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SimulatedMarketCard(MarketDisplayModel):
    market_id: str | None = None
    condition_id: str | None = None
    question: str
    category: str | None = None
    end_date: datetime | None = None
    yes_token_id: str | None = None
    no_token_id: str | None = None
    yes_price: Decimal | None = None
    no_price: Decimal | None = None
    yes_probability_pct: Decimal | None = None
    no_probability_pct: Decimal | None = None
    liquidity: Decimal | None = None
    volume: Decimal | None = None
    volume_24h: Decimal | None = None
    spread: Decimal | None = None
    last_trade_price: Decimal | None = None
    position_side: str | None = None
    position_size: Decimal = Decimal("0")
    avg_entry: Decimal | None = None
    current_price: Decimal | None = None
    current_value: Decimal = Decimal("0")
    cost_basis: Decimal = Decimal("0")
    pnl: Decimal = Decimal("0")
    pnl_pct: Decimal | None = None
    strategy_name: str | None = None
    last_signal_reason: str | None = None


class SimulatedTradeDisplayRow(MarketDisplayModel):
    time: datetime | None = None
    strategy: str | None = None
    action: str
    market_question: str
    side: str | None = None
    price: Decimal
    size: Decimal
    notional: Decimal
    reason_code: str | None = None
