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
    OPERATOR_CONSOLE_LAYOUT,
    OPERATOR_CONSOLE_SEVERITIES,
    OPERATOR_CONSOLE_STATUS_FIELDS,
    SIMULATION_CURVE_COLUMNS,
)
from polymarket_quant.ui.i18n import render_language_selector, t


DEFAULT_ARTIFACT_ROOT = Path(
    os.environ.get("POLYMARKET_QUANT_ARTIFACT_ROOT", ".artifacts/strategy_runs")
)


def build_overview_dataframe(rows: list[dict[str, Any]], language: str = "en") -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.copy()
        if "mode" in frame:
            frame["mode"] = frame["mode"].map(lambda value: _localize_mode(str(value), language=language))
        if "state" in frame:
            frame["state"] = frame["state"].map(lambda value: _localize_state(str(value), language=language))
        if "new_order_status" in frame:
            frame["new_order_status"] = frame["new_order_status"].map(
                lambda value: _localize_new_order_status(str(value), language=language)
            )
    return frame.rename(
        columns={
            "strategy_name": t(language, "operator.col_strategy_name"),
            "mode": t(language, "operator.col_mode"),
            "state": t(language, "operator.col_state"),
            "active_positions": t(language, "operator.col_active_positions"),
            "open_orders": t(language, "operator.col_open_orders"),
            "latest_pnl": t(language, "operator.col_latest_pnl"),
            "latest_drawdown": t(language, "operator.col_latest_drawdown"),
            "alerts": t(language, "operator.col_alerts"),
            "new_order_status": t(language, "operator.col_new_order_status"),
            "last_heartbeat": t(language, "operator.col_last_heartbeat"),
        }
    ).reindex(
        columns=[
            t(language, "operator.col_strategy_name"),
            t(language, "operator.col_mode"),
            t(language, "operator.col_state"),
            t(language, "operator.col_active_positions"),
            t(language, "operator.col_open_orders"),
            t(language, "operator.col_latest_pnl"),
            t(language, "operator.col_latest_drawdown"),
            t(language, "operator.col_alerts"),
            t(language, "operator.col_new_order_status"),
            t(language, "operator.col_last_heartbeat"),
        ]
    )


def build_positions_orders_dataframe(
    rows: list[dict[str, Any]], *, pane: str, language: str = "en"
) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if pane == "Positions":
        columns = [
            ("strategy_name", t(language, "operator.col_strategy_name")),
            ("token_id", t(language, "operator.col_token_id")),
            ("quantity", t(language, "operator.col_quantity")),
            ("mark_price", t(language, "operator.col_mark_price")),
            ("run_id", t(language, "operator.col_run_id")),
        ]
    else:
        columns = [
            ("strategy_name", t(language, "operator.col_strategy_name")),
            ("client_order_id", t(language, "operator.col_client_order_id")),
            ("token_id", t(language, "operator.col_token_id")),
            ("status", t(language, "operator.col_status")),
            ("run_id", t(language, "operator.col_run_id")),
        ]
    return frame.reindex(columns=[source for source, _label in columns]).rename(
        columns={source: label for source, label in columns}
    )


def build_pnl_exposure_dataframe(rows: list[dict[str, Any]], language: str = "en") -> pd.DataFrame:
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
    ).rename(
        columns={
            "strategy_name": t(language, "operator.col_strategy_name"),
            "realized_pnl": t(language, "operator.col_realized_pnl"),
            "unrealized_pnl": t(language, "operator.col_unrealized_pnl"),
            "turnover": t(language, "operator.col_turnover"),
            "max_drawdown": t(language, "operator.col_max_drawdown"),
            "exposure_peak": t(language, "operator.col_exposure_peak"),
            "win_rate": t(language, "operator.col_win_rate"),
            "run_id": t(language, "operator.col_run_id"),
        }
    )


def build_timeline_dataframe(rows: list[dict[str, Any]], language: str = "en") -> pd.DataFrame:
    return pd.DataFrame(rows).reindex(columns=["ts", "severity", "strategy", "message"]).rename(
        columns={
            "ts": t(language, "operator.col_ts"),
            "severity": t(language, "operator.col_severity"),
            "strategy": t(language, "operator.col_strategy"),
            "message": t(language, "operator.col_message"),
        }
    )


def build_simulation_curves_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows).reindex(columns=SIMULATION_CURVE_COLUMNS)
    if frame.empty:
        return frame
    frame = frame.copy()
    frame["ts"] = pd.to_datetime(frame["ts"])
    for column in ["equity", "pnl", "drawdown", "exposure"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    return frame.sort_values("ts")


def build_simulation_positions_dataframe(
    rows: list[dict[str, Any]], language: str = "en"
) -> pd.DataFrame:
    columns = [
        ("market", t(language, "operator.col_market")),
        ("direction", t(language, "operator.col_direction")),
        ("avg_price", t(language, "operator.col_avg_price")),
        ("current_price", t(language, "operator.col_current_price")),
        ("quantity", t(language, "operator.col_quantity")),
        ("cost", t(language, "operator.col_cost")),
        ("market_value", t(language, "operator.col_market_value")),
        ("pnl", t(language, "operator.col_pnl")),
        ("strategy", t(language, "operator.col_strategy")),
    ]
    return pd.DataFrame(rows).reindex(columns=[source for source, _label in columns]).rename(
        columns={source: label for source, label in columns}
    )


def build_simulation_trades_dataframe(
    rows: list[dict[str, Any]], language: str = "en"
) -> pd.DataFrame:
    columns = [
        ("time", t(language, "operator.col_time")),
        ("strategy", t(language, "operator.col_strategy")),
        ("action", t(language, "operator.col_action")),
        ("market", t(language, "operator.col_market")),
        ("direction", t(language, "operator.col_direction")),
        ("price", t(language, "operator.col_price")),
        ("quantity", t(language, "operator.col_quantity")),
        ("amount", t(language, "operator.col_amount")),
        ("reason_code", t(language, "operator.col_reason_code")),
    ]
    return pd.DataFrame(rows).reindex(columns=[source for source, _label in columns]).rename(
        columns={source: label for source, label in columns}
    )


def main(query_service: OperatorQueryService | None = None) -> None:
    if st is None:
        raise RuntimeError("streamlit is required to run the operator console")

    language = st.session_state.get("operator_console_language", "en") if st is not None else "en"
    st.set_page_config(page_title=t(language, "operator.page_title"), layout="wide")
    _inject_style()
    language = render_language_selector("operator_console_language")
    st.title(t(language, "operator.page_title"))
    st.caption(t(language, "operator.caption"))

    query_service = query_service or OperatorQueryService(DEFAULT_ARTIFACT_ROOT)
    filters = render_shared_filters()
    page = render_page_navigation(language)

    if page == "dashboard":
        render_simulation_dashboard(query_service, filters, language=language)
    elif page == "run_details":
        render_run_details_page(query_service, filters, language=language)
    elif page == "system_health":
        render_system_health_page(query_service, filters, language=language)
    else:
        render_debug_page(query_service, filters, language=language)


def render_page_navigation(language: str = "en") -> str:
    if st is None:
        return "dashboard"
    page_options = {
        t(language, "operator.nav_dashboard"): "dashboard",
        t(language, "operator.nav_run_details"): "run_details",
        t(language, "operator.nav_system_health"): "system_health",
        t(language, "operator.nav_debug"): "debug",
    }
    selected = st.sidebar.radio(
        t(language, "operator.nav"),
        list(page_options.keys()),
        key="operator_console_page",
    )
    return page_options[selected]


def render_simulation_dashboard(
    query_service: OperatorQueryService,
    filters: OperatorFilters,
    *,
    language: str = "en",
) -> None:
    if st is None:
        return

    summary = query_service.simulation_summary(filters)
    curve_rows = query_service.simulation_curves(filters)
    position_rows = query_service.simulation_positions(filters)
    trade_rows = query_service.simulation_trades(filters)
    alert_summary = query_service.risk_alert_summary(filters)

    st.subheader(t(language, "operator.results"))
    render_result_metrics(summary, language=language)

    st.subheader(t(language, "operator.curves"))
    render_result_curves(curve_rows, language=language)

    left, right = st.columns([3, 2])
    with left:
        st.subheader(t(language, "operator.current_positions"))
        positions = build_simulation_positions_dataframe(position_rows, language=language)
        if positions.empty:
            st.caption(t(language, "operator.no_positions"))
        st.dataframe(positions, use_container_width=True, hide_index=True)
    with right:
        render_risk_summary(alert_summary, language=language)

    st.subheader(t(language, "operator.recent_trades"))
    trades = build_simulation_trades_dataframe(trade_rows, language=language)
    if trades.empty:
        st.caption(t(language, "operator.no_trades"))
    st.dataframe(trades, use_container_width=True, hide_index=True)


def render_run_details_page(
    query_service: OperatorQueryService,
    filters: OperatorFilters,
    *,
    language: str = "en",
) -> None:
    if st is None:
        return
    st.caption(t(language, "operator.run_details_caption"))
    overview_rows = query_service.overview(group_by="strategy", filters=filters)
    positions_orders = query_service.positions_orders(filters)
    pnl_rows = query_service.pnl_exposure(filters)

    st.subheader(t(language, "operator.overview"))
    st.dataframe(
        build_overview_dataframe(overview_rows, language=language),
        use_container_width=True,
        hide_index=True,
    )
    left, right = st.columns(2)
    with left:
        render_positions_orders_block(positions_orders, language=language)
    with right:
        render_pnl_exposure_block(pnl_rows, language=language)
    render_runs_artifacts_surface(query_service, filters, language=language, expanded=True)


def render_system_health_page(
    query_service: OperatorQueryService,
    filters: OperatorFilters,
    *,
    language: str = "en",
) -> None:
    if st is None:
        return
    st.caption(t(language, "operator.system_health_caption"))
    render_status_band(query_service.status_band(filters), language=language)
    render_mode_switch(query_service, filters, language=language)


def render_debug_page(
    query_service: OperatorQueryService,
    filters: OperatorFilters,
    *,
    language: str = "en",
) -> None:
    if st is None:
        return
    st.caption(t(language, "operator.debug_caption"))
    st.subheader(t(language, "operator.timeline"))
    st.caption(t(language, "operator.timeline_caption"))
    st.dataframe(
        build_timeline_dataframe(query_service.alerts_timeline(filters), language=language),
        use_container_width=True,
        hide_index=True,
    )
    render_runs_artifacts_surface(query_service, filters, language=language, expanded=False)


def render_result_metrics(summary: dict[str, Any], *, language: str = "en") -> None:
    if st is None:
        return
    metric_rows = [
        [
            (t(language, "operator.metric_total_pnl"), summary.get("total_pnl")),
            (t(language, "operator.metric_today_pnl"), summary.get("today_pnl")),
            (t(language, "operator.metric_realized_pnl"), summary.get("realized_pnl")),
            (t(language, "operator.metric_unrealized_pnl"), summary.get("unrealized_pnl")),
        ],
        [
            (t(language, "operator.metric_current_exposure"), summary.get("current_exposure")),
            (t(language, "operator.metric_max_drawdown"), summary.get("max_drawdown")),
            (t(language, "operator.metric_positions"), summary.get("positions")),
            (t(language, "operator.metric_open_orders"), summary.get("open_orders")),
        ],
    ]
    for metric_row in metric_rows:
        columns = st.columns(4)
        for column, (label, value) in zip(columns, metric_row):
            with column:
                st.metric(label, _format_metric(value))


def render_result_curves(rows: list[dict[str, Any]], *, language: str = "en") -> None:
    if st is None:
        return
    curves = build_simulation_curves_dataframe(rows)
    if curves.empty:
        st.caption(t(language, "operator.no_curve"))
        return
    left, middle, right = st.columns(3)
    with left:
        st.caption(t(language, "operator.pnl_equity_curve"))
        st.line_chart(curves, x="ts", y=["pnl", "equity"], use_container_width=True)
    with middle:
        st.caption(t(language, "operator.drawdown_curve"))
        st.line_chart(curves, x="ts", y="drawdown", use_container_width=True)
    with right:
        st.caption(t(language, "operator.exposure_curve"))
        st.line_chart(curves, x="ts", y="exposure", use_container_width=True)


def render_risk_summary(alert_summary: dict[str, Any], *, language: str = "en") -> None:
    if st is None:
        return
    st.subheader(t(language, "operator.risk_summary"))
    st.caption(t(language, "operator.severity_ladder"))
    counts = alert_summary.get("counts", {})
    columns = st.columns(3)
    for column, severity in zip(columns, ["Critical", "Warning", "Info"]):
        with column:
            st.metric(severity, counts.get(severity, 0))
    latest = build_timeline_dataframe(alert_summary.get("latest", []), language=language)
    st.dataframe(latest, use_container_width=True, hide_index=True)


def render_shared_filters() -> OperatorFilters:
    if st is None:
        return OperatorFilters()

    language = st.session_state.get("operator_console_language", "en")
    st.sidebar.header(t(language, "operator.filters"))
    st.sidebar.caption(
        ", ".join(
            [
                t(language, "operator.filter_strategy"),
                t(language, "operator.filter_market_event"),
                t(language, "operator.filter_token"),
                t(language, "operator.filter_time_window"),
                t(language, "operator.filter_mode"),
                t(language, "operator.filter_severity"),
                t(language, "operator.filter_status"),
            ]
        )
    )
    strategy = st.sidebar.text_input(t(language, "operator.filter_strategy"))
    market = st.sidebar.text_input(t(language, "operator.filter_market_event"))
    token = st.sidebar.text_input(t(language, "operator.filter_token"))
    mode = st.sidebar.selectbox(
        t(language, "operator.filter_mode"),
        [
            "",
            t(language, "operator.mode_replay"),
            t(language, "operator.mode_paper"),
            t(language, "operator.mode_live_disabled"),
        ],
    )
    severity = st.sidebar.selectbox(t(language, "operator.filter_severity"), ["", *OPERATOR_CONSOLE_SEVERITIES])
    status = st.sidebar.selectbox(
        t(language, "operator.filter_status"),
        [
            "",
            t(language, "operator.status_running"),
            t(language, "operator.status_blocked"),
            t(language, "operator.status_warning"),
            t(language, "operator.status_paused"),
            t(language, "operator.status_error"),
            t(language, "operator.status_finished"),
        ],
    )
    time_window = st.sidebar.date_input(t(language, "operator.filter_time_window"), value=())
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
        mode=_normalize_mode_filter(mode, language=language),
        severity=severity or None,
        status=_normalize_status_filter(status, language=language),
        window_start=window_start,
        window_end=window_end,
    )


def render_status_band(status_band: dict[str, Any], *, language: str = "en") -> None:
    if st is None:
        return
    st.subheader(t(language, "operator.status_band"))
    columns = st.columns(len(OPERATOR_CONSOLE_STATUS_FIELDS))
    connections = status_band.get("connections", [])
    connection_summary = _render_connections_summary(connections, language=language)
    strategy_summary = status_band.get("strategy_summary", {})

    values = [
        _localize_mode(str(status_band.get("global_mode", "live-disabled")), language=language),
        connection_summary,
        _localize_strategy_summary(strategy_summary, language=language) or t(language, "operator.none"),
        _localize_new_order_status(
            str(status_band.get("new_order_status", "allowed")),
            language=language,
        ),
        str(status_band.get("high_priority_alerts", 0)),
        _format_timestamp(status_band.get("last_updated"), language=language),
    ]
    labels = [
        t(language, "operator.status_run_mode"),
        t(language, "operator.status_connection"),
        t(language, "operator.status_strategy"),
        t(language, "operator.status_new_order"),
        t(language, "operator.status_high_alerts"),
        t(language, "operator.status_last_heartbeat"),
    ]
    for column, label, value in zip(columns, labels, values):
        with column:
            st.caption(label)
            st.write(value)


def render_mode_switch(
    query_service: OperatorQueryService,
    filters: OperatorFilters,
    *,
    language: str = "en",
    safety_service: OperatorSafetyService | None = None,
) -> None:
    if st is None:
        return
    safety_service = safety_service or OperatorSafetyService()
    st.subheader(t(language, "operator.mode_switch"))
    target_mode_label = st.selectbox(
        t(language, "operator.target_global_mode"),
        [
            t(language, "operator.mode_replay"),
            t(language, "operator.mode_paper"),
            t(language, "operator.mode_live_disabled"),
        ],
        key="target_global_mode",
    )
    if st.button(t(language, "operator.preflight"), key="mode_preflight"):
        st.session_state["mode_preflight_result"] = build_mode_preflight(
            query_service,
            target_mode=target_mode_label,
            filters=filters,
            safety_service=safety_service,
            language=language,
        )

    preflight: ModePreflightResult | None = st.session_state.get("mode_preflight_result")
    if preflight is None:
        st.caption(t(language, "operator.preflight_hint"))
        return

    st.caption(
        t(language, "operator.preflight_target", target=preflight.target_mode.value)
    )
    if preflight.blockers:
        st.error("\n".join(preflight.blockers))
    if preflight.warnings:
        st.warning("\n".join(preflight.warnings))
    confirmed = st.checkbox(t(language, "operator.confirm_checkbox"), key="mode_switch_confirm")
    if st.button(
        t(language, "operator.confirm"),
        key="confirm_mode_switch",
        disabled=not preflight.allowed,
    ):
        if confirm_mode_switch(query_service, preflight, confirmed=confirmed):
            st.success(
                t(language, "operator.confirm_success", target=preflight.target_mode.value)
            )
        else:
            st.warning(t(language, "operator.confirm_required"))


def render_positions_orders_block(
    detail_rows: dict[str, list[dict[str, Any]]], *, language: str = "en"
) -> None:
    if st is None:
        return
    st.subheader(t(language, "operator.detail_positions_orders"))
    pane = st.selectbox(
        t(language, "operator.detail_positions_orders"),
        [t(language, "operator.positions"), t(language, "operator.orders")],
        key="positions_orders",
    )
    source_rows = (
        detail_rows["positions"]
        if pane == t(language, "operator.positions")
        else detail_rows["orders"]
    )
    st.dataframe(
        build_positions_orders_dataframe(
            source_rows,
            pane="Positions" if pane == t(language, "operator.positions") else "Orders",
            language=language,
        ),
        use_container_width=True,
        hide_index=True,
    )


def render_pnl_exposure_block(pnl_rows: list[dict[str, Any]], *, language: str = "en") -> None:
    if st is None:
        return
    st.subheader(t(language, "operator.detail_pnl_exposure"))
    st.caption(t(language, "operator.detail_pnl_exposure"))
    st.dataframe(
        build_pnl_exposure_dataframe(pnl_rows, language=language),
        use_container_width=True,
        hide_index=True,
    )


def render_runs_artifacts_surface(
    query_service: OperatorQueryService,
    filters: OperatorFilters,
    *,
    language: str = "en",
    expanded: bool = False,
) -> None:
    if st is None:
        return
    with st.expander(t(language, "operator.runs_artifacts"), expanded=expanded):
        st.caption(t(language, "operator.runs_artifacts_caption"))
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
    language: str = "en",
    safety_service: OperatorSafetyService | None = None,
) -> ModePreflightResult:
    filters = filters or OperatorFilters()
    safety_service = safety_service or OperatorSafetyService()
    status_band = query_service.status_band(filters)
    return safety_service.preflight(
        current_mode=status_band["global_mode"],
        target_mode=_global_mode_from_label(target_mode, language=language),
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


def _render_connections_summary(
    connections: list[ConnectionState], *, language: str = "en"
) -> str:
    if not connections:
        return t(language, "operator.none")
    return ", ".join(
        f"{connection.component.value}:{_localize_connection_status(connection.status.value, language=language)}"
        for connection in connections
    )


def _normalize_mode_filter(mode: str, *, language: str = "en") -> str | None:
    if mode == t(language, "operator.mode_paper"):
        return "realtime_paper"
    if mode == t(language, "operator.mode_replay"):
        return "replay"
    if mode == t(language, "operator.mode_live_disabled"):
        return "live-disabled"
    return None


def _normalize_status_filter(status: str, *, language: str = "en") -> str | None:
    mapping = {
        t(language, "operator.status_running"): "running",
        t(language, "operator.status_blocked"): "blocked",
        t(language, "operator.status_warning"): "blocked",
        t(language, "operator.status_paused"): "paused",
        t(language, "operator.status_error"): "error",
        t(language, "operator.status_finished"): "finished",
    }
    normalized = mapping.get(status, status or None)
    if normalized == "warning":
        return "blocked"
    return normalized


def _format_timestamp(value: Any, *, language: str = "en") -> str:
    if value is None:
        return t(language, "operator.na")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _format_metric(value: Any) -> str:
    if value is None:
        return "0"
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)
    if numeric.is_integer():
        return f"{numeric:,.0f}"
    return f"{numeric:,.4f}".rstrip("0").rstrip(".")


def _global_mode_from_label(value: str, *, language: str = "en") -> GlobalMode:
    if value == t(language, "operator.mode_paper"):
        return GlobalMode.PAPER
    if value == t(language, "operator.mode_replay"):
        return GlobalMode.REPLAY
    return GlobalMode.LIVE_DISABLED


def _localize_mode(value: str, *, language: str = "en") -> str:
    mapping = {
        "replay": t(language, "operator.mode_replay"),
        "realtime_paper": t(language, "operator.mode_paper"),
        "paper": t(language, "operator.mode_paper"),
        "live-disabled": t(language, "operator.mode_live_disabled"),
    }
    return mapping.get(value, value)


def _localize_state(value: str, *, language: str = "en") -> str:
    mapping = {
        "running": t(language, "operator.status_running"),
        "blocked": t(language, "operator.status_blocked"),
        "paused": t(language, "operator.status_paused"),
        "error": t(language, "operator.status_error"),
        "finished": t(language, "operator.status_finished"),
        "starting": "starting" if language == "en" else "启动中",
    }
    return mapping.get(value, value)


def _localize_new_order_status(value: str, *, language: str = "en") -> str:
    mapping = {
        "allowed": t(language, "operator.new_order_allowed"),
        "partially blocked": t(language, "operator.new_order_partially_blocked"),
        "fully blocked": t(language, "operator.new_order_fully_blocked"),
    }
    return mapping.get(value, value)


def _localize_connection_status(value: str, *, language: str = "en") -> str:
    mapping = {
        "healthy": t(language, "operator.connection_healthy"),
        "degraded": t(language, "operator.connection_degraded"),
        "down": t(language, "operator.connection_down"),
    }
    return mapping.get(value, value)


def _localize_strategy_summary(summary: dict[str, int], *, language: str = "en") -> str:
    localized_parts = []
    for name, count in summary.items():
        if not count:
            continue
        localized_parts.append(f"{_localize_state(name, language=language)}:{count}")
    return ", ".join(localized_parts)


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
