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


def build_latest_dataframe(rows: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(rows).reindex(columns=MARKET_DATA_COLUMNS)


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
    with st.expander("Data timeline", expanded=expanded):
        if not events:
            st.write("No data events yet.")
            return
        for event in events:
            st.write(
                f"{event.get('received_at', '')} | {event.get('source', '')} | "
                f"{event.get('status', 'ok')} | {event.get('message', '')}"
            )


def main() -> None:
    if st is None:
        raise RuntimeError("streamlit is required to run the market data app")

    st.set_page_config(page_title=MARKET_DATA_PAGE_TITLE, layout="wide")
    st.title(MARKET_DATA_PAGE_TITLE)
    st.caption("latest bid/ask, spread, midpoint, last price, source, gap fill")

    query_service = MarketDataQueryService(MarketDataStore())
    row_limit = st.sidebar.number_input(
        "Row limit",
        min_value=10,
        max_value=1000,
        value=100,
        step=10,
    )
    token_search = st.sidebar.text_input("Token search")
    show_gap_rows = st.sidebar.checkbox("Show gap fill rows", value=True)

    latest = query_service.latest_state_dataframe(limit=int(row_limit))
    filtered = apply_market_data_filters(
        latest,
        token_search=token_search,
        show_gap_rows=show_gap_rows,
        row_limit=int(row_limit),
    )
    st.dataframe(filtered[MARKET_DATA_COLUMNS], use_container_width=True, hide_index=True)

    selected_token = None
    if not filtered.empty:
        selected_token = st.selectbox(
            "Price curve token",
            filtered["token_id"].dropna().astype(str).tolist(),
        )
    if selected_token:
        series = query_service.price_series_dataframe(selected_token)
        chart_df = build_price_series_dataframe(series.to_dict(orient="records"))
        if not chart_df.empty:
            st.line_chart(chart_df, x="source_ts", y="price")
        else:
            st.write("No recent price curve yet.")

    render_timeline(
        filtered[["received_at", "source", "gap_fill"]]
        .rename(columns={"gap_fill": "status"})
        .to_dict(orient="records"),
        expanded=False,
    )


if __name__ == "__main__":
    main()
