from __future__ import annotations

from pathlib import Path

from polymarket_quant.ui.contracts import (
    OPERATOR_CONSOLE_DETAIL_PANES,
    OPERATOR_CONSOLE_FILTERS,
    OPERATOR_CONSOLE_LAYOUT,
    OPERATOR_CONSOLE_OVERVIEW_COLUMNS,
    OPERATOR_CONSOLE_PAGE_TITLE,
    OPERATOR_CONSOLE_SEVERITIES,
    OPERATOR_CONSOLE_STATUS_FIELDS,
)
from polymarket_quant.ui.i18n import t
from polymarket_quant.ui.operator_console_app import (
    build_overview_dataframe,
    build_pnl_exposure_dataframe,
    build_positions_orders_dataframe,
    build_timeline_dataframe,
)


def test_operator_console_contract_matches_phase5_context() -> None:
    assert OPERATOR_CONSOLE_PAGE_TITLE == "Operator Console"
    assert OPERATOR_CONSOLE_STATUS_FIELDS == [
        "Run Mode",
        "Connection Status",
        "Strategy Status",
        "New Order Status",
        "High Priority Alerts",
        "last heartbeat",
    ]
    assert OPERATOR_CONSOLE_FILTERS == [
        "strategy",
        "market/event",
        "token",
        "time window",
        "mode",
        "severity",
        "status",
    ]
    assert OPERATOR_CONSOLE_OVERVIEW_COLUMNS == [
        "strategy name",
        "mode",
        "state",
        "active positions",
        "open orders",
        "latest pnl",
        "latest drawdown",
        "alerts",
        "new order status",
        "last heartbeat",
    ]
    assert OPERATOR_CONSOLE_DETAIL_PANES == ["Positions / Orders", "PnL / Exposure"]
    assert OPERATOR_CONSOLE_SEVERITIES == ["Critical", "Warning", "Info"]
    assert OPERATOR_CONSOLE_LAYOUT == {
        "status_band": "top-fixed",
        "filters": "left",
        "overview": "main-upper",
        "details": "main-lower",
        "timeline": "bottom",
    }


def test_operator_console_dataframe_helpers_keep_contract_columns() -> None:
    overview = build_overview_dataframe(
        [
            {
                "strategy_name": "mean-reversion",
                "mode": "replay",
                "state": "running",
                "active_positions": 1,
                "open_orders": 2,
                "latest_pnl": 12.5,
                "latest_drawdown": 1.2,
                "alerts": 2,
                "new_order_status": "allowed",
                "last_heartbeat": "2026-04-22T08:00:00Z",
            }
        ]
    )
    positions = build_positions_orders_dataframe(
        [{"strategy_name": "mean-reversion", "token_id": "token-yes", "quantity": "5"}],
        pane="Positions",
    )
    pnl = build_pnl_exposure_dataframe(
        [{"strategy_name": "mean-reversion", "realized_pnl": 1, "run_id": "run-a"}]
    )
    timeline = build_timeline_dataframe(
        [{"ts": "2026-04-22T08:00:00Z", "severity": "Critical", "message": "blocked"}]
    )

    assert list(overview.columns) == OPERATOR_CONSOLE_OVERVIEW_COLUMNS
    assert "token_id" in positions.columns
    assert "exposure_peak" in pnl.columns
    assert "run_id" in pnl.columns
    assert list(timeline.columns) == ["ts", "severity", "strategy", "message"]


def test_operator_console_can_render_chinese_labels() -> None:
    overview = build_overview_dataframe(
        [
            {
                "strategy_name": "mean-reversion",
                "mode": "replay",
                "state": "running",
                "active_positions": 1,
                "open_orders": 2,
                "latest_pnl": 12.5,
                "latest_drawdown": 1.2,
                "alerts": 2,
                "new_order_status": "allowed",
                "last_heartbeat": "2026-04-22T08:00:00Z",
            }
        ],
        language="zh",
    )
    positions = build_positions_orders_dataframe(
        [{"strategy_name": "mean-reversion", "token_id": "token-yes", "quantity": "5"}],
        pane="Positions",
        language="zh",
    )
    pnl = build_pnl_exposure_dataframe(
        [{"strategy_name": "mean-reversion", "realized_pnl": 1, "run_id": "run-a"}],
        language="zh",
    )
    timeline = build_timeline_dataframe(
        [{"ts": "2026-04-22T08:00:00Z", "severity": "Critical", "message": "blocked"}],
        language="zh",
    )

    assert t("zh", "operator.col_strategy_name") in overview.columns
    assert t("zh", "operator.col_token_id") in positions.columns
    assert t("zh", "operator.col_realized_pnl") in pnl.columns
    assert list(timeline.columns) == [
        t("zh", "operator.col_ts"),
        t("zh", "operator.col_severity"),
        t("zh", "operator.col_strategy"),
        t("zh", "operator.col_message"),
    ]


def test_operator_console_is_single_page_not_tab_first() -> None:
    source = Path("src/polymarket_quant/ui/operator_console_app.py").read_text()

    assert "def main(" in source
    assert "st.sidebar" in source
    assert "Language / 语言" in source or "render_language_selector" in source
    assert "operator.col_last_heartbeat" in source
    assert "operator.detail_positions_orders" in source
    assert "operator.detail_pnl_exposure" in source
    assert "st.tabs(" not in source
