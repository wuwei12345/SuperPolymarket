from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from polymarket_quant.domain.market import (
    CanonicalMarket,
    MarketSourceMap,
    SourceLabel,
)


def source_map() -> MarketSourceMap:
    return MarketSourceMap(
        question=SourceLabel.GAMMA,
        category=SourceLabel.GAMMA,
        liquidity=SourceLabel.GAMMA,
        end_date=SourceLabel.GAMMA,
        condition_id=SourceLabel.NORMALIZED,
        yes_token_id=SourceLabel.CLOB,
        no_token_id=SourceLabel.CLOB,
    )


def market(**overrides: object) -> CanonicalMarket:
    values = {
        "market_id": "gamma-1",
        "question": "Will the test pass?",
        "category": "Testing",
        "liquidity": 123.45,
        "end_date": datetime(2026, 5, 1, tzinfo=timezone.utc),
        "condition_id": "0x" + "a" * 64,
        "yes_token_id": "1" * 78,
        "no_token_id": "2" * 78,
        "active": True,
        "accepting_orders": True,
        "restricted": False,
        "source_map": source_map(),
        "raw_gamma": {"id": "gamma-1"},
        "raw_clob": {"condition_id": "0x" + "a" * 64},
    }
    values.update(overrides)
    return CanonicalMarket(**values)


def test_valid_market_instantiates_with_source_labels() -> None:
    record = market()

    assert record.condition_id.startswith("0x")
    assert record.source_map.question is SourceLabel.GAMMA
    assert record.source_map.yes_token_id is SourceLabel.CLOB
    assert record.source_map.condition_id is SourceLabel.NORMALIZED


@pytest.mark.parametrize("field", ["condition_id", "yes_token_id", "no_token_id"])
def test_blank_ids_are_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        market(**{field: "   "})


@pytest.mark.parametrize(
    ("active", "accepting_orders"),
    [(False, True), (True, False), (False, False)],
)
def test_phase1_valid_rejects_inactive_or_non_accepting_markets(
    active: bool, accepting_orders: bool
) -> None:
    record = market(active=active, accepting_orders=accepting_orders)

    assert not record.is_phase1_valid()


def test_phase1_valid_accepts_active_accepting_complete_market() -> None:
    assert market().is_phase1_valid()
