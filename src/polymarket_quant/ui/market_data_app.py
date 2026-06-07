from __future__ import annotations

from typing import Any

import pandas as pd

try:
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover - Streamlit is installed for app use.
    st = None  # type: ignore[assignment]

from polymarket_quant.services.market_data_queries import MarketDataQueryService
from polymarket_quant.storage.market_data_store import MarketDataStore
from polymarket_quant.ui.contracts import (
    MARKET_DATA_COLUMNS,
    MARKET_DATA_PAGE_TITLE,
)
from polymarket_quant.ui.i18n import render_language_selector, t


def build_latest_dataframe(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows).reindex(columns=MARKET_DATA_COLUMNS)


def build_latest_display_dataframe(
    rows: list[dict[str, object]], language: str = "en"
) -> pd.DataFrame:
    return build_latest_dataframe(rows).rename(
        columns={
            "question": t(language, "market_data.col_question"),
            "token_id": t(language, "market_data.col_token_id"),
            "outcome": t(language, "market_data.col_outcome"),
            "best_bid": t(language, "market_data.col_best_bid"),
            "best_ask": t(language, "market_data.col_best_ask"),
            "spread": t(language, "market_data.col_spread"),
            "midpoint": t(language, "market_data.col_midpoint"),
            "last_trade_price": t(language, "market_data.col_last_trade"),
            "source": t(language, "market_data.col_source"),
            "gap_fill": t(language, "market_data.col_gap_fill"),
        }
    )


def build_price_series_dataframe(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows).reindex(
        columns=[
            "token_id",
            "question",
            "outcome",
            "price",
            "source_ts",
            "received_at",
            "source",
            "gap_fill",
        ]
    )


def build_price_series_display_dataframe(
    rows: list[dict[str, object]], language: str = "en"
) -> pd.DataFrame:
    return build_price_series_dataframe(rows).rename(
        columns={
            "token_id": t(language, "market_data.col_token_id"),
            "question": t(language, "market_data.col_question"),
            "outcome": t(language, "market_data.col_outcome"),
            "price": t(language, "market_data.col_price"),
            "source_ts": t(language, "market_data.col_source_ts"),
            "received_at": t(language, "market_data.col_received_at"),
            "source": t(language, "market_data.col_source"),
            "gap_fill": t(language, "market_data.col_gap_fill"),
        }
    )


def apply_market_data_filters(
    df: pd.DataFrame,
    token_search: str = "",
    show_gap_rows: bool = True,
    row_limit: int = 100,
) -> pd.DataFrame:
    result = df.copy()
    token_search = token_search.strip().lower()
    if token_search and "token_id" in result:
        result = result[
            result["token_id"]
            .fillna("")
            .str.lower()
            .str.contains(token_search, regex=False)
        ]
    if not show_gap_rows and "gap_fill" in result:
        result = result[result["gap_fill"] != True]  # noqa: E712
    return result.head(row_limit)


def render_timeline(events: list[dict[str, Any]], expanded: bool = False) -> None:
    if st is None:
        return
    language = st.session_state.get("market_data_language", "en")
    with st.expander(t(language, "market_data.timeline"), expanded=expanded):
        if not events:
            st.write(t(language, "market_data.no_events"))
            return
        for event in events:
            st.write(
                f"{event.get('received_at', '')} | {event.get('source', '')} | "
                f"{event.get('status', 'ok')} | {event.get('message', '')}"
            )


def main() -> None:
    if st is None:
        raise RuntimeError("streamlit is required to run the market data app")

    language = st.session_state.get("market_data_language", "en") if st is not None else "en"
    st.set_page_config(page_title=t(language, "market_data.page_title"), layout="wide")
    language = render_language_selector("market_data_language")
    st.title(t(language, "market_data.page_title"))
    st.caption(t(language, "market_data.caption"))

    query_service = MarketDataQueryService(MarketDataStore())
    row_limit = st.sidebar.number_input(
        t(language, "market_data.row_limit"),
        min_value=10,
        max_value=1000,
        value=100,
        step=10,
    )
    token_search = st.sidebar.text_input(t(language, "market_data.token_search"))
    show_gap_rows = st.sidebar.checkbox(t(language, "market_data.show_gap_rows"), value=True)

    latest = query_service.latest_state_dataframe(limit=int(row_limit))
    filtered = apply_market_data_filters(
        latest,
        token_search=token_search,
        show_gap_rows=show_gap_rows,
        row_limit=int(row_limit),
    )
    st.dataframe(
        build_latest_display_dataframe(filtered.to_dict(orient="records"), language=language),
        width="stretch",
        hide_index=True,
    )

    selected_token = None
    if not filtered.empty:
        selected_token = st.selectbox(
            t(language, "market_data.price_curve_token"),
            filtered["token_id"].dropna().astype(str).tolist(),
        )
    if selected_token:
        series = query_service.price_series_dataframe(selected_token)
        chart_df = build_price_series_display_dataframe(
            series.to_dict(orient="records"),
            language=language,
        )
        if not chart_df.empty:
            st.line_chart(
                chart_df,
                x=t(language, "market_data.col_source_ts"),
                y=t(language, "market_data.col_price"),
            )
        else:
            st.write(t(language, "market_data.no_recent_curve"))

    render_timeline(
        filtered[["received_at", "source", "gap_fill"]]
        .rename(columns={"gap_fill": "status"})
        .to_dict(orient="records"),
        expanded=False,
    )


if __name__ == "__main__":
    main()
