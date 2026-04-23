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
from polymarket_quant.ui.i18n import render_language_selector, t


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


def build_market_display_dataframe(df: pd.DataFrame, language: str = "en") -> pd.DataFrame:
    return df.rename(
        columns={
            "question": t(language, "market_universe.col_question"),
            "category": t(language, "market_universe.col_category"),
            "liquidity": t(language, "market_universe.col_liquidity"),
            "endDate": t(language, "market_universe.col_end_date"),
            "conditionId": t(language, "market_universe.col_condition_id"),
            "yes token": t(language, "market_universe.col_yes_token"),
            "no token": t(language, "market_universe.col_no_token"),
            "source": t(language, "market_universe.col_source"),
        }
    )


def apply_ui_filters(df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    result = df.copy()
    question_search = str(filters.get("question_search") or "").strip().lower()
    category = filters.get("category")
    minimum_liquidity = filters.get("minimum_liquidity")
    end_date_range = filters.get("end_date_range")
    restricted_status = filters.get("restricted_status")

    if question_search and "question" in result:
        result = result[
            result["question"]
            .fillna("")
            .str.lower()
            .str.contains(question_search, regex=False)
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
        language = st.session_state.get("market_universe_language", "en")
        st.caption(t(language, "market_universe.no_data_title"))

    language = st.session_state.get("market_universe_language", "en")
    with st.expander(t(language, "market_universe.timeline"), expanded=expanded):
        if not events:
            st.write(t(language, "market_universe.no_data_body"))
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

    language = st.session_state.get("market_universe_language", "en") if st is not None else "en"
    st.set_page_config(page_title=t(language, "market_universe.page_title"), layout="wide")
    _inject_style()
    language = render_language_selector("market_universe_language")

    store = MarketStore(DEFAULT_DB_PATH)
    if "sync_events" not in st.session_state:
        st.session_state["sync_events"] = []

    header_left, header_right = st.columns([4, 1])
    with header_left:
        st.title(t(language, "market_universe.page_title"))
        st.caption(t(language, "market_universe.caption"))
    with header_right:
        if st.button(t(language, "market_universe.primary_cta"), use_container_width=True):
            service = MarketSyncService(
                gamma_client=GammaClient(),
                clob_client=ClobClient(),
                store=store,
            )
            result = service.sync_once()
            st.session_state["sync_events"] = result.events
            if result.errors and result.written_count == 0:
                st.error(t(language, "market_universe.sync_failed"))
            else:
                st.success(t(language, "market_universe.sync_success"))

    markets = store.list_markets()
    df = build_market_dataframe(markets)
    filters = _render_filters(df)
    filtered = apply_ui_filters(df, filters)
    display_df = build_market_display_dataframe(filtered[DEFAULT_COLUMNS], language=language)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            t(language, "market_universe.col_liquidity"): st.column_config.NumberColumn(
                t(language, "market_universe.col_liquidity"),
                format="%.2f",
            )
        },
    )

    if df.empty:
        st.subheader(t(language, "market_universe.no_data_title"))
        st.write(t(language, "market_universe.no_data_body"))
    elif filtered.empty:
        st.subheader(t(language, "market_universe.no_match_title"))
        st.write(t(language, "market_universe.no_match_body"))

    render_timeline(st.session_state["sync_events"], expanded=False)


def _render_filters(df: pd.DataFrame) -> dict[str, Any]:
    language = st.session_state.get("market_universe_language", "en")
    st.sidebar.header(t(language, "market_universe.filters"))
    all_label = t(language, "market_universe.all")
    categories = [all_label]
    if not df.empty:
        categories.extend(sorted(value for value in df["category"].dropna().unique()))

    category_choice = st.sidebar.selectbox(
        t(language, "market_universe.filter_category"), categories
    )
    minimum_liquidity = st.sidebar.number_input(
        t(language, "market_universe.filter_min_liquidity"),
        min_value=0.0,
        value=0.0,
        step=100.0,
    )
    end_date_range = st.sidebar.date_input(
        t(language, "market_universe.filter_end_date"),
        value=(),
    )
    restricted_choice = st.sidebar.selectbox(
        t(language, "market_universe.filter_restricted"),
        [
            all_label,
            t(language, "market_universe.restricted"),
            t(language, "market_universe.unrestricted"),
        ],
    )
    question_search = st.sidebar.text_input(t(language, "market_universe.filter_question"))

    restricted_status = {
        t(language, "market_universe.restricted"): True,
        t(language, "market_universe.unrestricted"): False,
    }.get(restricted_choice)
    filters = {
        "category": None if category_choice == all_label else category_choice,
        "minimum_liquidity": minimum_liquidity,
        "end_date_range": end_date_range if len(end_date_range) == 2 else None,
        "restricted_status": restricted_status,
        "question_search": question_search,
    }
    st.sidebar.caption(
        t(language, "market_universe.active_filter_count", count=_active_filter_count(filters))
    )
    return filters


def _active_filter_count(filters: dict[str, Any]) -> int:
    count = 0
    if filters.get("category") is not None:
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
    language = st.session_state.get("market_universe_language", "en") if st is not None else "en"
    return (
        f"{t(language, 'market_universe.source_question')}:{source_map.question.value}; "
        f"{t(language, 'market_universe.source_liquidity')}:{source_map.liquidity.value}; "
        f"{t(language, 'market_universe.source_condition')}:{source_map.condition_id.value}; "
        f"{t(language, 'market_universe.source_tokens')}:{source_map.yes_token_id.value}"
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
