from __future__ import annotations

from pathlib import Path

from polymarket_quant.ui.contracts import (
    PRODUCT_STRATEGY_SIMPLE_FIELDS,
    SIMULATION_APP_HOME_SECTIONS,
    SIMULATION_APP_PAGES,
    SIMULATION_APP_PAGE_TITLE,
)
from polymarket_quant.ui.operator_console_app import (
    build_simulation_positions_dataframe,
    build_trade_display_dataframe,
)
from polymarket_quant.ui.i18n import t
from polymarket_quant.ui.simulation_dashboard_app import (
    MAX_HOME_CURVE_POINTS,
    _downsample_rows,
    _market_card_html,
    build_markets_payload,
    build_home_payload,
)


class FakeQueryService:
    def simulation_summary(self, filters):
        return {
            "total_pnl": "1.25",
            "today_pnl": "1.25",
            "realized_pnl": "1",
            "unrealized_pnl": "0.25",
            "current_exposure": "10",
            "max_drawdown": "0.5",
            "positions": 1,
            "open_orders": 0,
        }

    def simulation_curves(self, filters):
        return [{"ts": "2026-04-24T12:00:00Z", "pnl": "1.25", "equity": "1001.25", "run_id": "run-a"}]

    def simulation_positions(self, filters):
        return [
            {
                "market": "Will it rain?",
                "direction": "long",
                "avg_price": "0.50",
                "current_price": "0.55",
                "quantity": "20",
                "cost": "10",
                "market_value": "11",
                "pnl": "1",
                "strategy": "default_probe",
                "token_id": "token-yes",
                "run_id": "run-a",
            }
        ]

    def risk_alert_summary(self, filters):
        return {"counts": {"Critical": 0, "Warning": 0, "Info": 0}, "latest": []}


class FakeMarketDisplayService:
    def __init__(self) -> None:
        self.market_cards_called = False

    def recent_trades(self, filters):
        return [
            {
                "time": "2026-04-24T12:00:00Z",
                "strategy": "default_probe",
                "action": "enter",
                "market_question": "Will it rain?",
                "side": "YES",
                "price": "0.50",
                "size": "20",
                "notional": "10",
                "reason_code": "default_probe_enter",
                "run_id": "run-a",
            }
        ]

    def market_cards(self, filters):
        self.market_cards_called = True
        return [
            {
                "question": "Will it rain?",
                "yes_probability_pct": "55",
                "no_probability_pct": "45",
                "liquidity": "1000",
                "volume_24h": "250",
                "end_date": "2026-04-30T00:00:00Z",
                "position_side": "YES",
                "position_size": "20",
                "pnl": "1",
                "token_id": "token-yes",
                "condition_id": "condition-1",
            }
        ]


def test_simulation_dashboard_app_contract_is_product_first() -> None:
    assert SIMULATION_APP_PAGE_TITLE == "SuperPolymarket"
    assert SIMULATION_APP_PAGES == ["Dashboard", "Markets", "Strategy", "Advanced / Debug"]
    assert SIMULATION_APP_HOME_SECTIONS == [
        "Results",
        "Return Curve",
        "Markets",
        "Current Positions",
        "Recent Actions",
        "Risk Summary",
    ]
    assert PRODUCT_STRATEGY_SIMPLE_FIELDS == [
        "risk_level",
        "stake_per_trade",
        "max_positions",
    ]


def test_simulation_dashboard_app_has_english_and_chinese_copy() -> None:
    keys = [
        "app.page_title",
        "app.nav_dashboard",
        "app.nav_markets",
        "app.nav_strategy",
        "app.nav_advanced",
        "dashboard.results",
        "dashboard.curve",
        "dashboard.positions",
        "dashboard.recent_actions",
        "dashboard.risk",
        "markets.yes",
        "markets.no",
        "markets.volume_24h",
        "markets.liquidity",
        "markets.ends",
        "strategy.risk_level",
        "strategy.stake_per_trade",
        "strategy.max_positions",
        "strategy.advanced_yaml",
        "advanced.run_details",
        "advanced.system_health",
        "advanced.debug",
    ]

    for language in ("en", "zh"):
        for key in keys:
            assert t(language, key) != key


def test_home_payload_reads_result_first_surfaces(tmp_path: Path) -> None:
    payload = build_home_payload(
        FakeQueryService(),
        market_display_service=FakeMarketDisplayService(),
        snapshot_path=tmp_path / "missing-snapshot.json",
    )

    assert payload["summary"]["total_pnl"] == "1.25"
    assert payload["positions"][0]["market"] == "Will it rain?"
    assert payload["trades"][0]["market_question"] == "Will it rain?"
    assert payload["market_cards"][0]["yes_probability_pct"] == "55"
    assert payload["risk"]["counts"]["Critical"] == 0


def test_home_payload_downsamples_large_curve_from_snapshot(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "latest_snapshot.json"
    snapshot_path.write_text(
        __import__("json").dumps(
            {
                "summary_cards": {},
                "curves": [{"ts": f"2026-04-24T00:{index % 60:02d}:00Z", "pnl": index, "equity": index} for index in range(5000)],
                "current_positions": [],
                "recent_simulated_trades_display": [],
                "market_cards": [],
                "alert_summary": {},
            }
        )
    )

    payload = build_home_payload(
        FakeQueryService(),
        market_display_service=FakeMarketDisplayService(),
        snapshot_path=snapshot_path,
    )

    assert len(payload["curves"]) <= MAX_HOME_CURVE_POINTS
    assert payload["curves"][0]["pnl"] == 0
    assert payload["curves"][-1]["pnl"] == 4999


def test_markets_payload_uses_snapshot_cards_without_market_store_scan(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "latest_snapshot.json"
    snapshot_path.write_text(
        __import__("json").dumps(
            {
                "market_cards": [
                    {"question": "snapshot market", "yes_probability_pct": "51"}
                ]
            }
        )
    )
    market_display = FakeMarketDisplayService()

    rows = build_markets_payload(
        market_display,
        snapshot_path=snapshot_path,
        limit=24,
    )

    assert rows == [{"question": "snapshot market", "yes_probability_pct": "51"}]
    assert market_display.market_cards_called is False


def test_downsample_rows_keeps_first_and_last_points() -> None:
    rows = [{"index": index} for index in range(10)]

    sampled = _downsample_rows(rows, max_points=4)

    assert len(sampled) == 4
    assert sampled[0]["index"] == 0
    assert sampled[-1]["index"] == 9


def test_home_display_helpers_hide_technical_identifiers(tmp_path: Path) -> None:
    payload = build_home_payload(
        FakeQueryService(),
        market_display_service=FakeMarketDisplayService(),
        snapshot_path=tmp_path / "missing-snapshot.json",
    )
    positions = build_simulation_positions_dataframe(payload["positions"])
    trades = build_trade_display_dataframe(payload["trades"])
    card_html = _market_card_html(payload["market_cards"][0])

    visible_columns = set(positions.columns) | set(trades.columns)
    assert "run_id" not in visible_columns
    assert "token_id" not in visible_columns
    assert "condition_id" not in visible_columns
    assert "token-yes" not in card_html
    assert "condition-1" not in card_html
    assert "Will it rain?" in card_html
    assert "YES" in card_html
    assert "NO" in card_html


def test_root_app_points_to_simulation_dashboard_entrypoint() -> None:
    source = Path("app.py").read_text()

    assert "polymarket_quant.ui.simulation_dashboard_app" in source
    assert "main()" in source
