PAGE_TITLE = "Market Universe"
PRIMARY_CTA = "Sync markets"
DEFAULT_COLUMNS = [
    "question",
    "category",
    "liquidity",
    "endDate",
    "conditionId",
    "yes token",
    "no token",
    "source",
]
REQUIRED_FILTERS = [
    "category",
    "minimum liquidity",
    "end date range",
    "restricted status",
    "question search",
]
TIMELINE_EVENT_TYPES = [
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
LAYOUT_REGIONS = {
    "filters": "left",
    "table": "right",
    "timeline": "bottom-collapsible",
}

MARKET_DATA_PAGE_TITLE = "Market Data Monitor"
MARKET_DATA_COLUMNS = [
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
MARKET_DATA_REQUIRED_SECTIONS = ["latest table", "price curve", "timeline log"]
MARKET_DATA_FORBIDDEN_COPY = ["Trade", "Order", "Wallet", "PnL", "Position"]

OPERATOR_CONSOLE_PAGE_TITLE = "Simulation Result Dashboard"
SIMULATION_DASHBOARD_PAGES = [
    "Simulation Dashboard",
    "Run Details",
    "System Health",
    "Debug",
]
SIMULATION_RESULT_METRICS = [
    "total pnl",
    "today pnl",
    "realized pnl",
    "unrealized pnl",
    "current exposure",
    "max drawdown",
    "positions",
    "open orders",
]
SIMULATION_POSITION_COLUMNS = [
    "market",
    "direction",
    "avg price",
    "current price",
    "quantity",
    "cost",
    "market value",
    "pnl",
    "strategy",
]
SIMULATION_TRADE_COLUMNS = [
    "time",
    "strategy",
    "action",
    "market",
    "direction",
    "price",
    "quantity",
    "amount",
    "reason_code",
]
SIMULATION_CURVE_COLUMNS = [
    "ts",
    "equity",
    "pnl",
    "drawdown",
    "exposure",
    "strategy",
    "run_id",
]
OPERATOR_CONSOLE_STATUS_FIELDS = [
    "Run Mode",
    "Connection Status",
    "Strategy Status",
    "New Order Status",
    "High Priority Alerts",
    "last heartbeat",
]
OPERATOR_CONSOLE_FILTERS = [
    "strategy",
    "market/event",
    "token",
    "time window",
    "mode",
    "severity",
    "status",
]
OPERATOR_CONSOLE_OVERVIEW_COLUMNS = [
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
OPERATOR_CONSOLE_DETAIL_PANES = ["Positions / Orders", "PnL / Exposure"]
OPERATOR_CONSOLE_SEVERITIES = ["Critical", "Warning", "Info"]
OPERATOR_CONSOLE_LAYOUT = {
    "result_metrics": "top",
    "curves": "main-upper",
    "positions": "main-middle",
    "trades": "main-lower",
    "risk_summary": "side-or-lower",
    "status_band": "secondary-system-health",
    "filters": "left",
    "overview": "secondary-run-details",
    "details": "secondary-run-details",
    "timeline": "secondary-debug",
}
