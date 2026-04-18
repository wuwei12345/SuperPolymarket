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
