from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceLabel(str, Enum):
    GAMMA = "Gamma"
    CLOB = "CLOB"
    NORMALIZED = "Normalized"


class MarketSourceMap(BaseModel):
    question: SourceLabel
    category: SourceLabel
    liquidity: SourceLabel
    end_date: SourceLabel
    condition_id: SourceLabel
    yes_token_id: SourceLabel
    no_token_id: SourceLabel


class CanonicalMarket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    market_id: str | None = None
    question: str
    category: str | None = None
    liquidity: float | None = None
    end_date: datetime | None = None
    condition_id: str = Field(min_length=1)
    yes_token_id: str = Field(min_length=1)
    no_token_id: str = Field(min_length=1)
    active: bool
    accepting_orders: bool
    restricted: bool | None = None
    source_map: MarketSourceMap
    raw_gamma: dict[str, Any] | None = None
    raw_clob: dict[str, Any] | None = None

    @field_validator("condition_id", "yes_token_id", "no_token_id")
    @classmethod
    def required_ids_are_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("required market identifiers cannot be blank")
        return value

    def is_phase1_valid(self) -> bool:
        required_ids = (self.condition_id, self.yes_token_id, self.no_token_id)
        return (
            self.active
            and self.accepting_orders
            and all(identifier.strip() for identifier in required_ids)
        )
