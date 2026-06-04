from datetime import datetime, timezone

from polymarket_quant.domain.market import (
    CanonicalMarket,
    MarketSourceMap,
    SourceLabel,
)
from polymarket_quant.storage.market_store import MarketStore


LONG_CONDITION_ID = "0x" + "f" * 64
LONG_YES_TOKEN_ID = "1" * 78
LONG_NO_TOKEN_ID = "2" * 78


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
        "question": "Will this market remain active?",
        "category": "Politics",
        "liquidity": 2500.25,
        "end_date": datetime(2099, 6, 1, tzinfo=timezone.utc),
        "condition_id": LONG_CONDITION_ID,
        "yes_token_id": LONG_YES_TOKEN_ID,
        "no_token_id": LONG_NO_TOKEN_ID,
        "active": True,
        "accepting_orders": True,
        "restricted": False,
        "source_map": source_map(),
        "raw_gamma": {"id": "gamma-1", "liquidity": "2500.25"},
        "raw_clob": {"condition_id": LONG_CONDITION_ID},
    }
    values.update(overrides)
    return CanonicalMarket(**values)


def test_market_round_trips_full_ids_and_source_map(tmp_db_path) -> None:
    store = MarketStore(tmp_db_path)

    assert store.upsert_markets([market()]) == 1
    [stored] = store.list_markets()

    assert stored.condition_id == LONG_CONDITION_ID
    assert stored.yes_token_id == LONG_YES_TOKEN_ID
    assert stored.no_token_id == LONG_NO_TOKEN_ID
    assert stored.source_map.question is SourceLabel.GAMMA
    assert stored.source_map.yes_token_id is SourceLabel.CLOB
    assert stored.raw_gamma == {"id": "gamma-1", "liquidity": "2500.25"}


def test_invalid_markets_are_not_inserted(tmp_db_path) -> None:
    store = MarketStore(tmp_db_path)

    written = store.upsert_markets([market(active=False)])

    assert written == 0
    assert store.list_markets() == []


def test_list_markets_filters_active_accepting_only(tmp_db_path) -> None:
    store = MarketStore(tmp_db_path)
    store.upsert_markets(
        [
            market(condition_id="0x" + "a" * 64, category="Politics", liquidity=50.0),
            market(
                condition_id="0x" + "b" * 64,
                category="Sports",
                liquidity=1000.0,
                restricted=True,
            ),
            market(condition_id="0x" + "c" * 64, category="Politics", active=False),
            market(
                condition_id="0x" + "d" * 64,
                category="Politics",
                accepting_orders=False,
            ),
        ]
    )

    all_markets = store.list_markets()
    politics = store.list_markets(category="Politics")
    liquid = store.list_markets(min_liquidity=500)
    restricted = store.list_markets(restricted=True)

    assert [record.condition_id for record in all_markets] == [
        "0x" + "b" * 64,
        "0x" + "a" * 64,
    ]
    assert [record.condition_id for record in politics] == ["0x" + "a" * 64]
    assert [record.condition_id for record in liquid] == ["0x" + "b" * 64]
    assert [record.condition_id for record in restricted] == ["0x" + "b" * 64]


def test_list_markets_hides_expired_markets(tmp_db_path) -> None:
    store = MarketStore(tmp_db_path)
    store.upsert_markets(
        [
            market(condition_id="0x" + "a" * 64),
            market(
                condition_id="0x" + "b" * 64,
                end_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            ),
        ]
    )

    assert [record.condition_id for record in store.list_markets()] == ["0x" + "a" * 64]
