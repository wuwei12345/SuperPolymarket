from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from polymarket_quant.domain.market import (
    CanonicalMarket,
    MarketSourceMap,
    SourceLabel,
)
from polymarket_quant.ui import contracts
from polymarket_quant.ui.market_universe_app import (
    apply_ui_filters,
    build_market_dataframe,
)


def test_default_columns_match_ui_spec() -> None:
    assert contracts.DEFAULT_COLUMNS == [
        "question",
        "category",
        "liquidity",
        "endDate",
        "conditionId",
        "yes token",
        "no token",
        "source",
    ]


def test_required_copy_and_layout_constants_match_ui_spec() -> None:
    assert contracts.PAGE_TITLE == "Market Universe"
    assert contracts.PRIMARY_CTA == "Sync markets"
    assert contracts.REQUIRED_FILTERS == [
        "category",
        "minimum liquidity",
        "end date range",
        "restricted status",
        "question search",
    ]
    assert contracts.LAYOUT_REGIONS == {
        "filters": "left",
        "table": "right",
        "timeline": "bottom-collapsible",
    }


def test_timeline_event_types_match_ui_spec() -> None:
    assert contracts.TIMELINE_EVENT_TYPES == [
        "Sync started",
        "Gamma fetch started",
        "Gamma fetch completed",
        "CLOB fetch started",
        "CLOB fetch completed",
        "Retry scheduled",
        "Retry failed",
        "Normalization completed",
        "Sync succeeded",
        "Sync failed",
    ]


def test_layout_has_no_detail_panel_region() -> None:
    assert "detail" not in contracts.LAYOUT_REGIONS
    assert "details" not in contracts.LAYOUT_REGIONS
    assert "detail panel" not in contracts.LAYOUT_REGIONS.values()


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
        "question": "Will table filters pass?",
        "category": "Testing",
        "liquidity": 1000.0,
        "end_date": datetime(2026, 6, 1, tzinfo=timezone.utc),
        "condition_id": "0x" + "a" * 64,
        "yes_token_id": "yes-token",
        "no_token_id": "no-token",
        "active": True,
        "accepting_orders": True,
        "restricted": False,
        "source_map": source_map(),
    }
    values.update(overrides)
    return CanonicalMarket(**values)


def test_build_market_dataframe_uses_default_table_columns() -> None:
    df = build_market_dataframe([market()])

    assert list(df[contracts.DEFAULT_COLUMNS].columns) == contracts.DEFAULT_COLUMNS
    assert df.loc[0, "source"] == (
        "question:Gamma; liquidity:Gamma; condition:Normalized; tokens:CLOB"
    )


def test_apply_ui_filters_immediately_reduces_rows() -> None:
    df = build_market_dataframe(
        [
            market(condition_id="0x" + "a" * 64, category="Testing", liquidity=1000.0),
            market(
                condition_id="0x" + "b" * 64,
                category="Politics",
                liquidity=50.0,
                restricted=True,
            ),
        ]
    )

    filtered = apply_ui_filters(
        df,
        {
            "category": "Testing",
            "minimum_liquidity": 500,
            "question_search": "filters",
            "restricted_status": False,
            "end_date_range": None,
        },
    )

    assert filtered["conditionId"].tolist() == ["0x" + "a" * 64]


def test_ui_module_does_not_define_out_of_scope_surfaces() -> None:
    source = Path("src/polymarket_quant/ui/market_universe_app.py").read_text()

    for forbidden in ["Trade", "PnL", "wallet", "WebSocket"]:
        assert forbidden not in source


def test_dataframe_filter_handles_empty_input() -> None:
    df = pd.DataFrame(columns=[*contracts.DEFAULT_COLUMNS, "_restricted"])

    filtered = apply_ui_filters(df, {"question_search": "anything"})

    assert filtered.empty
