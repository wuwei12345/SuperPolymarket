from polymarket_quant.ui import contracts


def test_default_columns_match_ui_spec() -> None:
    assert contracts.DEFAULT_COLUMNS == [
        "question",
        "category",
        "liquidity",
        "endDate",
        "conditionId",
        "yes token",
        "no token",
        "source",
    ]


def test_required_copy_and_layout_constants_match_ui_spec() -> None:
    assert contracts.PAGE_TITLE == "Market Universe"
    assert contracts.PRIMARY_CTA == "Sync markets"
    assert contracts.REQUIRED_FILTERS == [
        "category",
        "minimum liquidity",
        "end date range",
        "restricted status",
        "question search",
    ]
    assert contracts.LAYOUT_REGIONS == {
        "filters": "left",
        "table": "right",
        "timeline": "bottom-collapsible",
    }


def test_timeline_event_types_match_ui_spec() -> None:
    assert contracts.TIMELINE_EVENT_TYPES == [
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


def test_layout_has_no_detail_panel_region() -> None:
    assert "detail" not in contracts.LAYOUT_REGIONS
    assert "details" not in contracts.LAYOUT_REGIONS
    assert "detail panel" not in contracts.LAYOUT_REGIONS.values()
