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
