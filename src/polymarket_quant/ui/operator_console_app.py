from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover - Streamlit is installed in normal app use.
    st = None  # type: ignore[assignment]

from polymarket_quant.domain.operator import ConnectionState, GlobalMode
from polymarket_quant.services.operator_queries import OperatorFilters, OperatorQueryService
from polymarket_quant.services.operator_safety import (
    ModePreflightResult,
    OperatorSafetyService,
)
from polymarket_quant.ui.contracts import (
    OPERATOR_CONSOLE_DETAIL_PANES,
    OPERATOR_CONSOLE_FILTERS,
    OPERATOR_CONSOLE_LAYOUT,
    OPERATOR_CONSOLE_OVERVIEW_COLUMNS,
    OPERATOR_CONSOLE_PAGE_TITLE,
    OPERATOR_CONSOLE_SEVERITIES,
    OPERATOR_CONSOLE_STATUS_FIELDS,
)


DEFAULT_ARTIFACT_ROOT = Path(
    os.environ.get("POLYMARKET_QUANT_ARTIFACT_ROOT", ".artifacts/strategy_runs")
)


def build_overview_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    return frame.rename(
        columns={
            "strategy_name": "strategy name",
            "active_positions": "active positions",
            "open_orders": "open orders",
            "latest_pnl": "latest pnl",
            "latest_drawdown": "latest drawdown",
            "new_order_status": "new order status",
            "last_heartbeat": "last heartbeat",
        }
    ).reindex(columns=OPERATOR_CONSOLE_OVERVIEW_COLUMNS)


def build_positions_orders_dataframe(rows: list[dict[str, Any]], *, pane: str) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if pane == "Positions":
        columns = [
            "strategy_name",
            "token_id",
            "quantity",
            "mark_price",
            "run_id",
        ]
    else:
        columns = [
            "strategy_name",
            "client_order_id",
            "token_id",
            "status",
            "run_id",
        ]
    return frame.reindex(columns=columns)


def build_pnl_exposure_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows).reindex(
        columns=[
            "strategy_name",
            "realized_pnl",
            "unrealized_pnl",
            "turnover",
            "max_drawdown",
            "exposure_peak",
            "win_rate",
            "run_id",
        ]
    )


def build_timeline_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows).reindex(columns=["ts", "severity", "strategy", "message"])


def main(query_service: OperatorQueryService | None = None) -> None:
    if st is None:
        raise RuntimeError("streamlit is required to run the operator console")

    st.set_page_config(page_title=OPERATOR_CONSOLE_PAGE_TITLE, layout="wide")
    _inject_style()
    st.title(OPERATOR_CONSOLE_PAGE_TITLE)
    st.caption("global mode, connection status, strategy state, alert summary, new-order block")
    st.caption("Severity ladder: Critical / Warning / Info")

    query_service = query_service or OperatorQueryService(DEFAULT_ARTIFACT_ROOT)
    filters = render_shared_filters()
    status_band = query_service.status_band(filters)
    overview_rows = query_service.overview(group_by="strategy", filters=filters)
    positions_orders = query_service.positions_orders(filters)
    pnl_rows = query_service.pnl_exposure(filters)
    timeline_rows = query_service.alerts_timeline(filters)

    render_status_band(status_band)
    st.subheader("Strategy Overview")
    st.dataframe(
        build_overview_dataframe(overview_rows),
        use_container_width=True,
        hide_index=True,
    )

    left, right = st.columns(2)
    with left:
        render_positions_orders_block(positions_orders)
    with right:
        render_pnl_exposure_block(pnl_rows)

    render_mode_switch(query_service, filters)
    st.subheader("Alerts Timeline")
    st.caption("read-only event flow with shared filters")
    st.dataframe(
        build_timeline_dataframe(timeline_rows),
        use_container_width=True,
        hide_index=True,
    )
    render_runs_artifacts_surface(query_service, filters)


def render_shared_filters() -> OperatorFilters:
    if st is None:
        return OperatorFilters()

    st.sidebar.header("Filters")
    st.sidebar.caption(", ".join(OPERATOR_CONSOLE_FILTERS))
    strategy = st.sidebar.text_input("strategy")
    market = st.sidebar.text_input("market/event")
    token = st.sidebar.text_input("token")
    mode = st.sidebar.selectbox("mode", ["", "replay", "paper", "live-disabled"])
    severity = st.sidebar.selectbox("severity", ["", *OPERATOR_CONSOLE_SEVERITIES])
    status = st.sidebar.selectbox(
        "status",
        ["", "running", "blocked", "warning", "paused", "error", "finished"],
    )
    time_window = st.sidebar.date_input("time window", value=())
    window_start = None
    window_end = None
    if len(time_window) == 2:
        window_start = pd.Timestamp(time_window[0]).to_pydatetime()
        window_end = pd.Timestamp(time_window[1]).to_pydatetime()
    return OperatorFilters(
        strategy=strategy or None,
        market=market or None,
        event=market or None,
        token=token or None,
        mode=_normalize_mode_filter(mode),
        severity=severity or None,
        status=_normalize_status_filter(status),
        window_start=window_start,
        window_end=window_end,
    )


def render_status_band(status_band: dict[str, Any]) -> None:
    if st is None:
        return
    st.subheader("Status Band")
    columns = st.columns(len(OPERATOR_CONSOLE_STATUS_FIELDS))
    connections = status_band.get("connections", [])
    connection_summary = _render_connections_summary(connections)
    strategy_summary = status_band.get("strategy_summary", {})
    strategy_text = ", ".join(
        f"{name}:{count}" for name, count in strategy_summary.items() if count
    ) or "none"

    values = [
        str(status_band.get("global_mode", "live-disabled")),
        connection_summary,
        strategy_text,
        str(status_band.get("new_order_status", "allowed")),
        str(status_band.get("high_priority_alerts", 0)),
        _format_timestamp(status_band.get("last_updated")),
    ]
    for column, label, value in zip(columns, OPERATOR_CONSOLE_STATUS_FIELDS, values):
        with column:
            st.caption(label)
            st.write(value)


def render_mode_switch(
    query_service: OperatorQueryService,
    filters: OperatorFilters,
    safety_service: OperatorSafetyService | None = None,
) -> None:
    if st is None:
        return
    safety_service = safety_service or OperatorSafetyService()
    st.subheader("Mode Switch")
    target_mode_label = st.selectbox(
        "Target global mode",
        ["replay", "paper", "live-disabled"],
        key="target_global_mode",
    )
    if st.button("Run preflight", key="mode_preflight"):
        st.session_state["mode_preflight_result"] = build_mode_preflight(
            query_service,
            target_mode=target_mode_label,
            filters=filters,
            safety_service=safety_service,
        )

    preflight: ModePreflightResult | None = st.session_state.get("mode_preflight_result")
    if preflight is None:
        st.caption("Run preflight before confirm.")
        return

    st.caption(f"preflight target={preflight.target_mode.value}")
    if preflight.blockers:
        st.error("\n".join(preflight.blockers))
    if preflight.warnings:
        st.warning("\n".join(preflight.warnings))
    confirmed = st.checkbox("I confirm the global mode change", key="mode_switch_confirm")
    if st.button(
        "confirm mode switch",
        key="confirm_mode_switch",
        disabled=not preflight.allowed,
    ):
        if confirm_mode_switch(query_service, preflight, confirmed=confirmed):
            st.success(f"Global mode changed to {preflight.target_mode.value}")
        else:
            st.warning("confirm is required before the mode changes.")


def render_positions_orders_block(detail_rows: dict[str, list[dict[str, Any]]]) -> None:
    if st is None:
        return
    st.subheader(OPERATOR_CONSOLE_DETAIL_PANES[0])
    pane = st.selectbox("Positions / Orders", ["Positions", "Orders"], key="positions_orders")
    source_rows = detail_rows["positions"] if pane == "Positions" else detail_rows["orders"]
    st.dataframe(
        build_positions_orders_dataframe(source_rows, pane=pane),
        use_container_width=True,
        hide_index=True,
    )


def render_pnl_exposure_block(pnl_rows: list[dict[str, Any]]) -> None:
    if st is None:
        return
    st.subheader(OPERATOR_CONSOLE_DETAIL_PANES[1])
    st.caption("PnL / Exposure")
    st.dataframe(
        build_pnl_exposure_dataframe(pnl_rows),
        use_container_width=True,
        hide_index=True,
    )


def render_runs_artifacts_surface(
    query_service: OperatorQueryService,
    filters: OperatorFilters,
) -> None:
    if st is None:
        return
    with st.expander("Runs / Artifacts", expanded=False):
        st.caption("secondary surface; not a homepage default pane")
        st.dataframe(
            pd.DataFrame(query_service.runs_artifacts(filters)),
            use_container_width=True,
            hide_index=True,
        )


def build_mode_preflight(
    query_service: OperatorQueryService,
    *,
    target_mode: str,
    filters: OperatorFilters | None = None,
    safety_service: OperatorSafetyService | None = None,
) -> ModePreflightResult:
    filters = filters or OperatorFilters()
    safety_service = safety_service or OperatorSafetyService()
    status_band = query_service.status_band(filters)
    return safety_service.preflight(
        current_mode=status_band["global_mode"],
        target_mode=_global_mode_from_label(target_mode),
        connections=status_band["connections"],
    )


def confirm_mode_switch(
    query_service: OperatorQueryService,
    preflight: ModePreflightResult,
    *,
    confirmed: bool,
) -> bool:
    if not confirmed or not preflight.allowed or query_service.runtime_registry is None:
        return False
    query_service.runtime_registry.set_global_mode(preflight.target_mode)
    return True


def _render_connections_summary(connections: list[ConnectionState]) -> str:
    if not connections:
        return "none"
    return ", ".join(f"{connection.component.value}:{connection.status.value}" for connection in connections)


def _normalize_mode_filter(mode: str) -> str | None:
    if mode == "paper":
        return "realtime_paper"
    if mode in {"replay", "live-disabled"}:
        return mode
    return None


def _normalize_status_filter(status: str) -> str | None:
    if status == "warning":
        return "blocked"
    return status or None


def _format_timestamp(value: Any) -> str:
    if value is None:
        return "n/a"
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _global_mode_from_label(value: str) -> GlobalMode:
    if value == "paper":
        return GlobalMode.PAPER
    if value == "replay":
        return GlobalMode.REPLAY
    return GlobalMode.LIVE_DISABLED


def _inject_style() -> None:
    if st is None:
        return
    st.markdown(
        f"""
        <style>
        .stApp {{ background: #F6F7F9; color: #1F2930; }}
        [data-testid="stSidebar"] {{ background: #FFFFFF; border-right: 1px solid #D7DDE2; }}
        div[data-testid="stDataFrame"] {{ border: 1px solid #D7DDE2; border-radius: 8px; }}
        .stMarkdown h2 {{ margin-top: 0.5rem; }}
        .stApp [data-testid="block-container"]::before {{
            content: "{OPERATOR_CONSOLE_LAYOUT['status_band']}";
            display: none;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
