from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover - Streamlit is installed in normal app use.
    st = None  # type: ignore[assignment]

from polymarket_quant.adapters.polymarket import ClobClient, GammaClient
from polymarket_quant.domain.market import CanonicalMarket, MarketSourceMap
from polymarket_quant.services.market_sync import MarketSyncService, SyncEvent
from polymarket_quant.storage.market_store import MarketStore
from polymarket_quant.ui.contracts import DEFAULT_COLUMNS, PAGE_TITLE, PRIMARY_CTA


DEFAULT_DB_PATH = Path(os.environ.get("POLYMARKET_QUANT_DB", ".data/market_universe.sqlite"))


def build_market_dataframe(markets: list[CanonicalMarket]) -> pd.DataFrame:
    rows = []
    for market in markets:
        rows.append(
            {
                "question": market.question,
                "category": market.category,
                "liquidity": market.liquidity,
                "endDate": _format_end_date(market),
                "conditionId": market.condition_id,
                "yes token": market.yes_token_id,
                "no token": market.no_token_id,
                "source": _source_summary(market.source_map),
                "_restricted": market.restricted,
            }
        )
    return pd.DataFrame(rows, columns=[*DEFAULT_COLUMNS, "_restricted"])


def apply_ui_filters(df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    result = df.copy()
    question_search = str(filters.get("question_search") or "").strip().lower()
    category = filters.get("category")
    minimum_liquidity = filters.get("minimum_liquidity")
    end_date_range = filters.get("end_date_range")
    restricted_status = filters.get("restricted_status")

    if question_search and "question" in result:
        result = result[
            result["question"].fillna("").str.lower().str.contains(question_search)
        ]
    if category and category != "All" and "category" in result:
        result = result[result["category"] == category]
    if minimum_liquidity not in (None, "") and "liquidity" in result:
        result = result[
            pd.to_numeric(result["liquidity"], errors="coerce").fillna(0)
            >= float(minimum_liquidity)
        ]
    if end_date_range and len(end_date_range) == 2 and "endDate" in result:
        start, end = end_date_range
        dates = pd.to_datetime(result["endDate"], errors="coerce", utc=True).dt.date
        if start:
            result = result[dates >= start]
            dates = pd.to_datetime(result["endDate"], errors="coerce", utc=True).dt.date
        if end:
            result = result[dates <= end]
    if restricted_status in {True, False} and "_restricted" in result:
        result = result[result["_restricted"] == restricted_status]

    return result


def render_timeline(events: list[SyncEvent], expanded: bool = False) -> None:
    if st is None:
        return

    latest = events[-1] if events else None
    if latest:
        st.caption(f"{latest.status}: {latest.step} - {latest.message}")
    else:
        st.caption("No market universe yet")

    with st.expander("Sync timeline", expanded=expanded):
        if not events:
            st.write("Sync markets to load active markets that are accepting orders.")
            return
        for event in events:
            timestamp = event.timestamp.isoformat(timespec="seconds")
            st.write(
                f"{timestamp} | {event.status} | {event.source} | "
                f"{event.step} | {event.message}"
            )


def main() -> None:
    if st is None:
        raise RuntimeError("streamlit is required to run the Market Universe app")

    st.set_page_config(page_title=PAGE_TITLE, layout="wide")
    _inject_style()

    store = MarketStore(DEFAULT_DB_PATH)
    if "sync_events" not in st.session_state:
        st.session_state["sync_events"] = []

    header_left, header_right = st.columns([4, 1])
    with header_left:
        st.title(PAGE_TITLE)
        st.caption("active + accepting orders")
    with header_right:
        if st.button(PRIMARY_CTA, use_container_width=True):
            service = MarketSyncService(
                gamma_client=GammaClient(),
                clob_client=ClobClient(),
                store=store,
            )
            result = service.sync_once()
            st.session_state["sync_events"] = result.events
            if result.errors and result.written_count == 0:
                st.error("Sync failed. Check the timeline and try again.")
            else:
                st.success("Market universe updated")

    markets = store.list_markets()
    df = build_market_dataframe(markets)
    filters = _render_filters(df)
    filtered = apply_ui_filters(df, filters)

    st.dataframe(
        filtered[DEFAULT_COLUMNS],
        use_container_width=True,
        hide_index=True,
        column_config={
            "liquidity": st.column_config.NumberColumn("liquidity", format="%.2f")
        },
    )

    if df.empty:
        st.subheader("No market universe yet")
        st.write("Sync markets to load active markets that are accepting orders.")
    elif filtered.empty:
        st.subheader("No markets match these filters")
        st.write("Change the filters or sync markets again.")

    render_timeline(st.session_state["sync_events"], expanded=False)


def _render_filters(df: pd.DataFrame) -> dict[str, Any]:
    st.sidebar.header("Filters")
    categories = ["All"]
    if not df.empty:
        categories.extend(sorted(value for value in df["category"].dropna().unique()))

    category = st.sidebar.selectbox("Category", categories)
    minimum_liquidity = st.sidebar.number_input(
        "Minimum liquidity",
        min_value=0.0,
        value=0.0,
        step=100.0,
    )
    end_date_range = st.sidebar.date_input("End date range", value=())
    restricted_choice = st.sidebar.selectbox(
        "Restricted status",
        ["All", "Restricted", "Unrestricted"],
    )
    question_search = st.sidebar.text_input("Question search")

    restricted_status = {
        "Restricted": True,
        "Unrestricted": False,
    }.get(restricted_choice)
    filters = {
        "category": category,
        "minimum_liquidity": minimum_liquidity,
        "end_date_range": end_date_range if len(end_date_range) == 2 else None,
        "restricted_status": restricted_status,
        "question_search": question_search,
    }
    st.sidebar.caption(f"{_active_filter_count(filters)} active")
    return filters


def _active_filter_count(filters: dict[str, Any]) -> int:
    count = 0
    if filters.get("category") not in (None, "All"):
        count += 1
    if filters.get("minimum_liquidity", 0) > 0:
        count += 1
    if filters.get("end_date_range"):
        count += 1
    if filters.get("restricted_status") is not None:
        count += 1
    if str(filters.get("question_search") or "").strip():
        count += 1
    return count


def _format_end_date(market: CanonicalMarket) -> str | None:
    if market.end_date is None:
        return None
    return market.end_date.isoformat()


def _source_summary(source_map: MarketSourceMap) -> str:
    return (
        f"question:{source_map.question.value}; "
        f"liquidity:{source_map.liquidity.value}; "
        f"condition:{source_map.condition_id.value}; "
        f"tokens:{source_map.yes_token_id.value}"
    )


def _inject_style() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #F6F7F9; color: #1F2930; }
        [data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #D7DDE2; }
        div[data-testid="stDataFrame"] { border: 1px solid #D7DDE2; border-radius: 8px; }
        .stButton button { border-radius: 8px; background: #0F8B8D; color: #FFFFFF; }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
