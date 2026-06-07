from __future__ import annotations

import html
import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd

try:
    import streamlit as st
except ModuleNotFoundError:  # pragma: no cover - Streamlit is installed in normal app use.
    st = None  # type: ignore[assignment]

from polymarket_quant.services.market_display import MarketDisplayService
from polymarket_quant.services.operator_queries import OperatorFilters, OperatorQueryService
from polymarket_quant.services.product_strategy_config import (
    DEFAULT_PRODUCT_CONFIG_PATH,
    ProductSimulationSettings,
    ProductStrategyConfig,
    ProductStrategySettings,
    ProductUniverseSettings,
    RiskLevel,
    dump_product_strategy_config,
    load_product_strategy_config,
    parse_product_strategy_config,
    product_config_to_runtime_config,
    save_product_strategy_config,
)
from polymarket_quant.storage.market_store import MarketStore
from polymarket_quant.ui.i18n import render_language_selector, t
from polymarket_quant.ui.operator_console_app import (
    DEFAULT_ARTIFACT_ROOT,
    DEFAULT_MARKET_STORE,
    DEFAULT_RUNTIME_SNAPSHOT,
    build_simulation_curves_dataframe,
    build_simulation_positions_dataframe,
    build_trade_display_dataframe,
    render_debug_page,
    render_risk_summary,
    render_run_details_page,
    render_shared_filters,
    render_system_health_page,
)


DEFAULT_APP_CONFIG_PATH = Path(
    os.environ.get("SUPERPOLYMARKET_STRATEGY_CONFIG", DEFAULT_PRODUCT_CONFIG_PATH)
)
MAX_HOME_CURVE_POINTS = 1200
MAX_MARKET_PAGE_CARDS = 24


def main(
    query_service: OperatorQueryService | None = None,
    *,
    market_display_service: MarketDisplayService | None = None,
) -> None:
    if st is None:
        raise RuntimeError("streamlit is required to run SuperPolymarket")

    language = st.session_state.get("simulation_dashboard_language", "en")
    st.set_page_config(page_title=t(language, "app.page_title"), layout="wide")
    _inject_app_style()
    language = render_language_selector("simulation_dashboard_language")

    st.title(t(language, "app.page_title"))
    st.caption(t(language, "app.caption"))

    query_service = query_service or OperatorQueryService(DEFAULT_ARTIFACT_ROOT)
    market_display_service = market_display_service or MarketDisplayService(
        market_store=MarketStore(DEFAULT_MARKET_STORE),
        query_service=query_service,
    )
    page = render_app_navigation(language)

    if page == "dashboard":
        render_home_dashboard(
            query_service,
            market_display_service=market_display_service,
            language=language,
        )
    elif page == "markets":
        render_markets_page(market_display_service, language=language)
    elif page == "strategy":
        render_strategy_page(DEFAULT_APP_CONFIG_PATH, language=language)
    else:
        render_advanced_page(query_service, language=language)


def render_app_navigation(language: str = "en") -> str:
    if st is None:
        return "dashboard"
    page_options = {
        t(language, "app.nav_dashboard"): "dashboard",
        t(language, "app.nav_markets"): "markets",
        t(language, "app.nav_strategy"): "strategy",
        t(language, "app.nav_advanced"): "advanced",
    }
    selected = st.sidebar.radio(
        t(language, "app.nav"),
        list(page_options.keys()),
        key="simulation_dashboard_page",
    )
    return page_options[selected]


def build_home_payload(
    query_service: OperatorQueryService,
    *,
    market_display_service: MarketDisplayService | None = None,
    filters: OperatorFilters | None = None,
    snapshot_path: str | Path = DEFAULT_RUNTIME_SNAPSHOT,
    max_curve_points: int = MAX_HOME_CURVE_POINTS,
) -> dict[str, Any]:
    filters = filters or OperatorFilters()
    snapshot = load_app_snapshot(snapshot_path) if _filters_are_empty(filters) else None
    return {
        "summary": snapshot.get("summary_cards", {})
        if snapshot is not None
        else query_service.simulation_summary(filters),
        "curves": _downsample_rows(snapshot.get("curves", []), max_points=max_curve_points)
        if snapshot is not None
        else _downsample_rows(
            query_service.simulation_curves(filters),
            max_points=max_curve_points,
        ),
        "positions": snapshot.get("current_positions", [])
        if snapshot is not None
        else query_service.simulation_positions(filters),
        "trades": snapshot.get("recent_simulated_trades_display", [])
        if snapshot is not None and snapshot.get("recent_simulated_trades_display")
        else market_display_service.recent_trades(filters)
        if market_display_service is not None
        else [],
        "market_cards": snapshot.get("market_cards", [])
        if snapshot is not None and snapshot.get("market_cards")
        else market_display_service.market_cards(filters)
        if market_display_service is not None
        else [],
        "risk": snapshot.get("alert_summary", {})
        if snapshot is not None
        else query_service.risk_alert_summary(filters),
    }


def render_home_dashboard(
    query_service: OperatorQueryService,
    *,
    market_display_service: MarketDisplayService,
    language: str = "en",
) -> None:
    if st is None:
        return
    payload = build_home_payload(
        query_service,
        market_display_service=market_display_service,
    )
    st.caption(f"{t(language, 'app.home_status_ready')} · {t(language, 'app.home_status_source')}")

    st.subheader(t(language, "dashboard.results"))
    render_home_metrics(payload["summary"], language=language)

    st.subheader(t(language, "dashboard.curve"))
    render_home_curve(payload["curves"], language=language)

    left, right = st.columns([3, 2])
    with left:
        st.subheader(t(language, "dashboard.markets"))
        render_market_card_grid(payload["market_cards"], language=language, limit=6)
    with right:
        st.subheader(t(language, "dashboard.risk"))
        render_risk_summary(payload["risk"], language=language)

    st.subheader(t(language, "dashboard.positions"))
    positions = build_simulation_positions_dataframe(payload["positions"], language=language)
    if positions.empty:
        st.caption(t(language, "dashboard.no_positions"))
    else:
        st.dataframe(positions, width="stretch", hide_index=True)

    st.subheader(t(language, "dashboard.recent_actions"))
    trades = build_trade_display_dataframe(payload["trades"], language=language)
    if trades.empty:
        st.caption(t(language, "dashboard.no_actions"))
    else:
        st.dataframe(trades, width="stretch", hide_index=True)


def render_home_metrics(summary: dict[str, Any], *, language: str = "en") -> None:
    if st is None:
        return
    metric_rows = [
        [
            (t(language, "dashboard.metric_total_pnl"), summary.get("total_pnl")),
            (t(language, "dashboard.metric_today_pnl"), summary.get("today_pnl")),
            (t(language, "dashboard.metric_realized_pnl"), summary.get("realized_pnl")),
            (t(language, "dashboard.metric_unrealized_pnl"), summary.get("unrealized_pnl")),
        ],
        [
            (t(language, "dashboard.metric_current_exposure"), summary.get("current_exposure")),
            (t(language, "dashboard.metric_max_drawdown"), summary.get("max_drawdown")),
            (t(language, "dashboard.metric_positions"), summary.get("positions")),
            (t(language, "dashboard.metric_open_orders"), summary.get("open_orders")),
        ],
    ]
    for metric_row in metric_rows:
        columns = st.columns(4)
        for column, (label, value) in zip(columns, metric_row):
            with column:
                st.metric(label, _format_number(value))


def render_home_curve(rows: list[dict[str, Any]], *, language: str = "en") -> None:
    if st is None:
        return
    curves = build_simulation_curves_dataframe(
        _downsample_rows(rows, max_points=MAX_HOME_CURVE_POINTS)
    )
    if curves.empty:
        st.caption(t(language, "operator.no_curve"))
        return
    display = curves.drop(columns=[column for column in ("strategy", "run_id") if column in curves])
    st.line_chart(display, x="ts", y=["pnl", "equity"], width="stretch")


def render_markets_page(
    market_display_service: MarketDisplayService,
    *,
    language: str = "en",
) -> None:
    if st is None:
        return
    st.caption(t(language, "markets.page_caption"))
    render_market_card_grid(
        build_markets_payload(market_display_service, limit=MAX_MARKET_PAGE_CARDS),
        language=language,
        limit=MAX_MARKET_PAGE_CARDS,
    )


def build_markets_payload(
    market_display_service: MarketDisplayService,
    *,
    snapshot_path: str | Path = DEFAULT_RUNTIME_SNAPSHOT,
    limit: int = MAX_MARKET_PAGE_CARDS,
) -> list[dict[str, Any]]:
    snapshot = load_app_snapshot(snapshot_path)
    if snapshot is not None and snapshot.get("market_cards"):
        return list(snapshot["market_cards"][:limit])
    return market_display_service.market_cards(OperatorFilters(), limit=limit)


def render_market_card_grid(
    rows: list[dict[str, Any]],
    *,
    language: str = "en",
    limit: int = 12,
) -> None:
    if st is None:
        return
    if not rows:
        st.caption(t(language, "dashboard.no_markets"))
        return
    for chunk_start in range(0, min(len(rows), limit), 3):
        columns = st.columns(3)
        for column, row in zip(columns, rows[chunk_start : chunk_start + 3]):
            with column:
                st.markdown(_market_card_html(row, language=language), unsafe_allow_html=True)


def render_strategy_page(config_path: Path, *, language: str = "en") -> None:
    if st is None:
        return
    config = load_product_strategy_config(config_path)
    st.caption(t(language, "strategy.page_caption"))

    simple_config = _render_strategy_simple_controls(config, language=language)
    yaml_text = dump_product_strategy_config(simple_config)
    advanced_yaml = st.checkbox(t(language, "strategy.advanced_yaml"), value=False)
    parsed_config = simple_config
    if advanced_yaml:
        yaml_text = st.text_area(
            t(language, "strategy.yaml"),
            value=yaml_text,
            height=320,
            key="product_strategy_yaml",
        )
        try:
            parsed_config = parse_product_strategy_config(yaml_text)
        except Exception as exc:
            st.error(t(language, "common.invalid_yaml", error=str(exc)))
            parsed_config = simple_config

    if st.button(t(language, "common.save"), key="save_product_strategy_config"):
        save_product_strategy_config(parsed_config, config_path)
        st.success(t(language, "strategy.save_success"))

    st.code(dump_product_strategy_config(parsed_config), language="yaml")
    if advanced_yaml:
        st.subheader(t(language, "strategy.runtime_preview"))
        st.json(product_config_to_runtime_config(parsed_config))


def render_advanced_page(
    query_service: OperatorQueryService,
    *,
    language: str = "en",
) -> None:
    if st is None:
        return
    st.caption(t(language, "advanced.caption"))
    filters = render_shared_filters()
    run_tab, health_tab, debug_tab = st.tabs(
        [
            t(language, "advanced.run_details"),
            t(language, "advanced.system_health"),
            t(language, "advanced.debug"),
        ]
    )
    with run_tab:
        render_run_details_page(query_service, filters, language=language)
    with health_tab:
        render_system_health_page(query_service, filters, language=language)
    with debug_tab:
        render_debug_page(query_service, filters, language=language)
        st.subheader(t(language, "advanced.legacy_pages"))
        st.caption(t(language, "advanced.market_universe"))
        st.code("streamlit run src/polymarket_quant/ui/market_universe_app.py", language="bash")
        st.caption(t(language, "advanced.market_data"))
        st.code("streamlit run src/polymarket_quant/ui/market_data_app.py", language="bash")


def _render_strategy_simple_controls(
    config: ProductStrategyConfig,
    *,
    language: str = "en",
) -> ProductStrategyConfig:
    risk_options = list(RiskLevel)
    selected_risk = st.selectbox(
        t(language, "strategy.risk_level"),
        risk_options,
        index=risk_options.index(config.strategy.risk_level),
        format_func=lambda risk: t(language, f"strategy.risk.{risk.value}"),
        key="product_strategy_risk_level",
    )
    stake = st.number_input(
        t(language, "strategy.stake_per_trade"),
        min_value=1.0,
        max_value=100000.0,
        value=float(config.strategy.stake_per_trade),
        step=1.0,
        key="product_strategy_stake_per_trade",
    )
    max_positions = st.number_input(
        t(language, "strategy.max_positions"),
        min_value=1,
        max_value=50,
        value=int(config.strategy.max_positions),
        step=1,
        key="product_strategy_max_positions",
    )
    return ProductStrategyConfig(
        strategy=ProductStrategySettings(
            name=config.strategy.name,
            risk_level=selected_risk,
            stake_per_trade=Decimal(str(stake)),
            max_positions=int(max_positions),
        ),
        universe=ProductUniverseSettings(
            min_liquidity=config.universe.min_liquidity,
            min_volume_24h=config.universe.min_volume_24h,
            max_days_to_expiry=config.universe.max_days_to_expiry,
        ),
        simulation=ProductSimulationSettings(
            starting_cash=config.simulation.starting_cash,
            mode=config.simulation.mode,
            environment=config.simulation.environment,
        ),
    )


def _market_card_html(row: dict[str, Any], *, language: str = "en") -> str:
    question = html.escape(str(row.get("question") or t(language, "common.na")))
    yes = _format_probability(row.get("yes_probability_pct"))
    no = _format_probability(row.get("no_probability_pct"))
    volume_24h = _format_money(row.get("volume_24h"))
    liquidity = _format_money(row.get("liquidity"))
    end_date = html.escape(_format_short_date(row.get("end_date"), language=language))
    position_side = row.get("position_side")
    position_size = _as_decimal(row.get("position_size"))
    position_html = ""
    if position_side and position_size != 0:
        position_html = f"""
        <div class="pm-position">
          <span>{html.escape(t(language, "markets.position"))}</span>
          <strong>{html.escape(str(position_side))} {_format_number(position_size)}</strong>
        </div>
        <div class="pm-position">
          <span>{html.escape(t(language, "markets.pnl"))}</span>
          <strong>{html.escape(_format_money(row.get("pnl")))}</strong>
        </div>
        """
    return f"""
    <div class="pm-card">
      <div class="pm-title">{question}</div>
      <div class="pm-prices">
        <div class="pm-price pm-yes"><span>{html.escape(t(language, "markets.yes"))}</span><strong>{yes}</strong></div>
        <div class="pm-price pm-no"><span>{html.escape(t(language, "markets.no"))}</span><strong>{no}</strong></div>
      </div>
      <div class="pm-meta">
        <span>{html.escape(t(language, "markets.volume_24h"))}: <b>{volume_24h}</b></span>
        <span>{html.escape(t(language, "markets.liquidity"))}: <b>{liquidity}</b></span>
        <span>{html.escape(t(language, "markets.ends"))}: <b>{end_date}</b></span>
      </div>
      {position_html}
    </div>
    """


def _filters_are_empty(filters: OperatorFilters) -> bool:
    return not any(
        [
            filters.strategy,
            filters.market,
            filters.event,
            filters.token,
            filters.mode,
            filters.severity,
            filters.status,
            filters.window_start,
            filters.window_end,
        ]
    )


def load_app_snapshot(path: str | Path = DEFAULT_RUNTIME_SNAPSHOT) -> dict[str, Any] | None:
    snapshot_path = Path(path)
    if not snapshot_path.exists():
        return None
    mtime_ns = snapshot_path.stat().st_mtime_ns
    if st is None:
        return _read_snapshot(snapshot_path)
    return _cached_app_snapshot(str(snapshot_path), mtime_ns)


if st is not None:

    @st.cache_data(show_spinner=False)
    def _cached_app_snapshot(path: str, mtime_ns: int) -> dict[str, Any] | None:
        _ = mtime_ns
        return _read_snapshot(Path(path))

else:

    def _cached_app_snapshot(path: str, mtime_ns: int) -> dict[str, Any] | None:
        _ = mtime_ns
        return _read_snapshot(Path(path))


def _read_snapshot(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _downsample_rows(rows: list[dict[str, Any]], *, max_points: int) -> list[dict[str, Any]]:
    if max_points <= 0 or len(rows) <= max_points:
        return list(rows)
    if max_points == 1:
        return [rows[-1]]
    step = (len(rows) - 1) / (max_points - 1)
    indexes = sorted({round(index * step) for index in range(max_points)})
    return [rows[index] for index in indexes]


def _format_probability(value: Any) -> str:
    numeric = _as_decimal(value)
    if numeric == 0:
        return "0%"
    return f"{numeric.quantize(Decimal('0.1'))}%"


def _format_money(value: Any) -> str:
    numeric = _as_decimal(value)
    return f"${numeric:,.2f}".rstrip("0").rstrip(".")


def _format_number(value: Any) -> str:
    numeric = _as_decimal(value)
    if numeric == 0:
        return "0"
    if numeric == numeric.to_integral_value():
        return f"{numeric:,.0f}"
    return f"{numeric:,.4f}".rstrip("0").rstrip(".")


def _format_short_date(value: Any, *, language: str = "en") -> str:
    if value in (None, ""):
        return t(language, "common.na")
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        return t(language, "common.na")
    return timestamp.strftime("%Y-%m-%d")


def _as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _inject_app_style() -> None:
    if st is None:
        return
    st.markdown(
        """
        <style>
        .stApp {
            background: #F4F6F5;
            color: #17201B;
            font-family: "Avenir Next", "IBM Plex Sans", sans-serif;
        }
        [data-testid="stSidebar"] {
            background: #FFFFFF;
            border-right: 1px solid #D9E0DC;
        }
        div[data-testid="stMetric"] {
            background: #FFFFFF;
            border: 1px solid #D9E0DC;
            border-radius: 8px;
            padding: 0.65rem 0.8rem;
        }
        div[data-testid="stDataFrame"] {
            border: 1px solid #D9E0DC;
            border-radius: 8px;
        }
        .pm-card {
            background: #FFFFFF;
            border: 1px solid #D9E0DC;
            border-radius: 8px;
            padding: 14px;
            min-height: 220px;
            margin-bottom: 14px;
            box-shadow: 0 1px 2px rgba(16, 24, 20, 0.05);
        }
        .pm-title {
            min-height: 54px;
            font-size: 0.98rem;
            font-weight: 700;
            line-height: 1.25;
            color: #17201B;
        }
        .pm-prices {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin: 12px 0;
        }
        .pm-price {
            border-radius: 6px;
            padding: 9px 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.82rem;
        }
        .pm-price strong {
            font-size: 1rem;
        }
        .pm-yes {
            background: #E7F6EE;
            color: #0D6B3A;
            border: 1px solid #BEE5CF;
        }
        .pm-no {
            background: #E9F0FA;
            color: #275C9A;
            border: 1px solid #C7D8F0;
        }
        .pm-meta,
        .pm-position {
            display: grid;
            gap: 5px;
            color: #58645D;
            font-size: 0.82rem;
        }
        .pm-position {
            grid-template-columns: 1fr auto;
            border-top: 1px solid #E6ECE8;
            padding-top: 8px;
            margin-top: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
