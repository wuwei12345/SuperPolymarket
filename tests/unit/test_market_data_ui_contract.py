from __future__ import annotations

from pathlib import Path

from polymarket_quant.ui.contracts import (
    MARKET_DATA_COLUMNS,
    MARKET_DATA_FORBIDDEN_COPY,
    MARKET_DATA_PAGE_TITLE,
    MARKET_DATA_REQUIRED_SECTIONS,
)
from polymarket_quant.ui.i18n import t
from polymarket_quant.ui.market_data_app import (
    apply_market_data_filters,
    build_latest_dataframe,
    build_latest_display_dataframe,
    build_price_series_dataframe,
    build_price_series_display_dataframe,
)


def test_market_data_columns_include_source_and_gap_fill() -> None:
    assert MARKET_DATA_PAGE_TITLE == "Market Data Monitor"
    assert MARKET_DATA_COLUMNS == [
        "question",
        "token_id",
        "outcome",
        "best_bid",
        "best_ask",
        "spread",
        "midpoint",
        "last_trade_price",
        "source",
        "gap_fill",
    ]
    assert "source" in MARKET_DATA_COLUMNS
    assert "gap_fill" in MARKET_DATA_COLUMNS
    assert MARKET_DATA_REQUIRED_SECTIONS == [
        "latest table",
        "price curve",
        "timeline log",
    ]


def test_market_data_dataframe_helpers_keep_contract_columns() -> None:
    df = build_latest_dataframe(
        [
            {
                "question": "Question",
                "token_id": "token-a",
                "outcome": "Yes",
                "best_bid": 0.44,
                "best_ask": 0.46,
                "spread": 0.02,
                "midpoint": 0.45,
                "last_trade_price": 0.45,
                "source": "CLOB_WS",
                "gap_fill": False,
            }
        ]
    )
    series = build_price_series_dataframe(
        [{"token_id": "token-a", "price": 0.45, "gap_fill": True}]
    )

    assert list(df.columns) == MARKET_DATA_COLUMNS
    assert bool(series.loc[0, "gap_fill"]) is True


def test_market_data_can_render_chinese_labels() -> None:
    df = build_latest_display_dataframe(
        [
            {
                "question": "Question",
                "token_id": "token-a",
                "outcome": "Yes",
                "best_bid": 0.44,
                "best_ask": 0.46,
                "spread": 0.02,
                "midpoint": 0.45,
                "last_trade_price": 0.45,
                "source": "CLOB_WS",
                "gap_fill": False,
            }
        ],
        language="zh",
    )
    series = build_price_series_display_dataframe(
        [{"token_id": "token-a", "price": 0.45, "gap_fill": True}],
        language="zh",
    )

    assert list(df.columns) == [
        t("zh", "market_data.col_question"),
        t("zh", "market_data.col_token_id"),
        t("zh", "market_data.col_outcome"),
        t("zh", "market_data.col_best_bid"),
        t("zh", "market_data.col_best_ask"),
        t("zh", "market_data.col_spread"),
        t("zh", "market_data.col_midpoint"),
        t("zh", "market_data.col_last_trade"),
        t("zh", "market_data.col_source"),
        t("zh", "market_data.col_gap_fill"),
    ]
    assert t("zh", "market_data.col_price") in series.columns


def test_market_data_filters_apply_immediately_to_dataframe() -> None:
    df = build_latest_dataframe(
        [
            {"token_id": "token-a", "gap_fill": False},
            {"token_id": "token-b", "gap_fill": True},
        ]
    )

    filtered = apply_market_data_filters(
        df,
        token_search="token-a",
        show_gap_rows=False,
        row_limit=10,
    )

    assert filtered["token_id"].tolist() == ["token-a"]


def test_market_data_token_search_treats_input_as_literal_text() -> None:
    df = build_latest_dataframe(
        [
            {"token_id": "token-[a]", "gap_fill": False},
            {"token_id": "token-b", "gap_fill": False},
        ]
    )

    filtered = apply_market_data_filters(df, token_search="[a]")

    assert filtered["token_id"].tolist() == ["token-[a]"]


def test_market_data_ui_does_not_define_trading_controls() -> None:
    source = Path("src/polymarket_quant/ui/market_data_app.py").read_text()

    for forbidden in MARKET_DATA_FORBIDDEN_COPY:
        assert forbidden not in source
    assert "MarketDataQueryService" in source
    assert "market_data.timeline" in source


def test_readme_documents_market_data_monitor_command() -> None:
    readme = Path("README.md").read_text()

    assert "## Phase 2 Market Data Monitor" in readme
    assert "streamlit run src/polymarket_quant/ui/market_data_app.py" in readme
    assert "gap-fill markers" in readme
    assert "python -m polymarket_quant.services.realtime_collector" in readme
