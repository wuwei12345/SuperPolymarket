from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MarketDataModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("token_id", check_fields=False)
    @classmethod
    def token_id_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("token_id cannot be blank")
        return value

    @field_validator("condition_id", check_fields=False)
    @classmethod
    def condition_id_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("condition_id cannot be blank")
        return value


class ReferenceToken(MarketDataModel):
    token_id: str = Field(min_length=1)
    condition_id: str | None = None
    market_id: str | None = None
    question: str
    outcome: Literal["Yes", "No"]
    category: str | None = None
    liquidity: Decimal | None = None
    end_date: datetime | None = None
    active: bool = True
    accepting_orders: bool = True
    universe_rank: int
    selection_reason: str
    created_at: datetime = Field(default_factory=utc_now)


class RawPayloadEnvelope(MarketDataModel):
    source: str
    endpoint: str
    payload: dict[str, Any] | list[Any]
    received_at: datetime = Field(default_factory=utc_now)
    token_id: str | None = None
    condition_id: str | None = None
    source_ts: datetime | None = None
    collection_run_id: str | None = None
    connection_id: str | None = None
    gap_fill: bool = False


class PriceHistoryPoint(MarketDataModel):
    token_id: str = Field(min_length=1)
    condition_id: str | None = None
    price: Decimal
    source_ts: datetime
    received_at: datetime = Field(default_factory=utc_now)
    source: str = "CLOB_REST"
    collection_run_id: str | None = None
    gap_fill: bool = False


class BookLevel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    side: Literal["BUY", "SELL"]
    price: Decimal
    size: Decimal


class BookSnapshot(MarketDataModel):
    token_id: str = Field(min_length=1)
    condition_id: str | None = None
    market: str | None = None
    source_ts: datetime | None = None
    received_at: datetime = Field(default_factory=utc_now)
    source: str = "CLOB_REST"
    hash: str | None = None
    bids: list[BookLevel] = Field(default_factory=list)
    asks: list[BookLevel] = Field(default_factory=list)
    min_order_size: Decimal | None = None
    tick_size: Decimal | None = None
    neg_risk: bool | None = None
    last_trade_price: Decimal | None = None
    collection_run_id: str | None = None
    gap_fill: bool = False


class BestBidAsk(MarketDataModel):
    token_id: str = Field(min_length=1)
    condition_id: str | None = None
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None
    spread: Decimal | None = None
    midpoint: Decimal | None = None
    source_ts: datetime | None = None
    received_at: datetime = Field(default_factory=utc_now)
    source: str = "Normalized"
    collection_run_id: str | None = None
    connection_id: str | None = None
    gap_fill: bool = False


class LastTrade(MarketDataModel):
    token_id: str = Field(min_length=1)
    condition_id: str | None = None
    price: Decimal
    side: str | None = None
    size: Decimal | None = None
    source_ts: datetime | None = None
    received_at: datetime = Field(default_factory=utc_now)
    source: str = "CLOB_REST"
    collection_run_id: str | None = None
    connection_id: str | None = None
    gap_fill: bool = False


class GapFillInterval(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token_ids: list[str]
    gap_started_at: datetime
    gap_ended_at: datetime
    connection_id: str | None = None
    reason: str = "websocket_reconnect"
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("token_ids")
    @classmethod
    def token_ids_are_not_blank(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("token_ids cannot be empty")
        if any(not token_id.strip() for token_id in value):
            raise ValueError("token_ids cannot contain blanks")
        return value
