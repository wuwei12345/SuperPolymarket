from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from polymarket_quant.domain.automation import (
    AutomationResolvedConfig,
    AutomationRun,
    ReportFormat,
    ReportReference,
)
from polymarket_quant.domain.strategy import RunMode
from polymarket_quant.services.automation_cli import (
    AutomationCliService,
    build_bootstrap_market_events,
    prepare_strategy_raw_config,
)
from polymarket_quant.services.automation_runner import AutomationRunResult


class StubRunner:
    def __init__(self, resolved_config: AutomationResolvedConfig) -> None:
        self.resolved_config = resolved_config

    def run(self, resolved_config: AutomationResolvedConfig) -> AutomationRunResult:
        assert resolved_config == self.resolved_config
        run = AutomationRun(
            run_id="automation-cli-001",
            environment="local",
            mode=RunMode.REALTIME_PAPER,
            started_at=resolved_config.model_fields_set and __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            resolved_config=resolved_config,
            report=ReportReference(
                window_start=__import__("datetime").datetime(2026, 4, 21, 0, 0, tzinfo=__import__("datetime").timezone.utc),
                window_end=__import__("datetime").datetime(2026, 4, 21, 23, 59, 59, tzinfo=__import__("datetime").timezone.utc),
                markdown_path=str(Path(resolved_config.report_output_dir) / "report.md"),
                html_path=str(Path(resolved_config.report_output_dir) / "report.html"),
            ),
        )
        run_directory = Path(resolved_config.automation_root) / run.run_id
        run_directory.mkdir(parents=True, exist_ok=True)
        return AutomationRunResult(run, run_directory)


def write_automation_config(path: Path) -> None:
    strategy_path = path.parent / "strategy.daily.yaml"
    strategy_path.write_text(
        yaml.safe_dump(
            {
                "run_id": "strategy-daily-001",
                "environment": "local",
                "mode": "realtime_paper",
                "strategy": {"name": "scheduled_bootstrap", "version": "0.1.0"},
                "universe": {"dataset_id": "dataset-001", "token_ids": [], "token_mappings": []},
                "risk": {"cash_available": "1000"},
            }
        )
    )
    path.write_text(
        yaml.safe_dump(
            {
                "environment": "local",
                "mode": "realtime_paper",
                "artifact_root": "data/runs",
                "automation_root": "data/automation",
                "report_output_dir": "data/reports/daily",
                "report_formats": ["markdown", "html"],
                "strategies": [
                    {
                        "name": "scheduled_bootstrap",
                        "strategy_class": "polymarket_quant.strategy.scheduled:ScheduledBootstrapStrategy",
                        "config_path": "strategy.daily.yaml",
                    }
                ],
            }
        )
    )


def test_cli_runs_automation_from_yaml_config(tmp_path: Path) -> None:
    config_path = tmp_path / "automation.daily.yaml"
    write_automation_config(config_path)
    cli = AutomationCliService(runner_factory=lambda resolved: StubRunner(resolved))

    result = cli.run(config_path)

    assert result.automation_run.run_id == "automation-cli-001"
    assert result.automation_run.resolved_config.mode == RunMode.REALTIME_PAPER


def test_cli_returns_report_paths_and_status(tmp_path: Path) -> None:
    config_path = tmp_path / "automation.daily.yaml"
    write_automation_config(config_path)
    cli = AutomationCliService(runner_factory=lambda resolved: StubRunner(resolved))

    result = cli.run(config_path)

    assert result.report is not None
    assert result.report.markdown_path.endswith("report.md")
    assert result.report.html_path.endswith("report.html")


def test_readme_documents_cron_without_internal_scheduler_claim() -> None:
    readme = Path("README.md").read_text()

    assert "cron" in readme
    assert "internal scheduler" not in readme.lower()


class FakeMarket:
    def __init__(
        self,
        *,
        market_id: str = "market-1",
        condition_id: str = "condition-1",
        question: str = "Will this sample market resolve yes?",
        category: str = "Politics",
        yes_token_id: str = "token-yes",
        no_token_id: str = "token-no",
        liquidity: float = 1000.0,
    ) -> None:
        self.market_id = market_id
        self.condition_id = condition_id
        self.question = question
        self.category = category
        self.yes_token_id = yes_token_id
        self.no_token_id = no_token_id
        self.liquidity = liquidity


class FakeMarketStore:
    def __init__(self, markets=None) -> None:
        self._markets = markets or [FakeMarket()]

    def list_markets(self):
        return self._markets


class FakeClobClient:
    def fetch_order_books(self, token_ids: list[str]):
        books = {
            "token-yes": {
                "asset_id": "token-yes",
                "market": "condition-1",
                "bids": [{"price": "0.44", "size": "25"}],
                "asks": [{"price": "0.46", "size": "25"}],
                "last_trade_price": "0.45",
                "tick_size": "0.01",
                "min_order_size": "1",
            },
            "token-wide": {
                "asset_id": "token-wide",
                "market": "condition-wide",
                "bids": [{"price": "0.01", "size": "25"}],
                "asks": [{"price": "0.02", "size": "25"}],
                "last_trade_price": "0.015",
                "tick_size": "0.01",
                "min_order_size": "1",
            },
            "token-balanced": {
                "asset_id": "token-balanced",
                "market": "condition-balanced",
                "bids": [{"price": "0.48", "size": "25"}],
                "asks": [{"price": "0.52", "size": "25"}],
                "last_trade_price": "0.50",
                "tick_size": "0.01",
                "min_order_size": "1",
            },
            "token-no": {
                "asset_id": "token-no",
                "market": "condition-1",
                "bids": [{"price": "0.54", "size": "25"}],
                "asks": [{"price": "0.56", "size": "25"}],
                "last_trade_price": "0.55",
                "tick_size": "0.01",
                "min_order_size": "1",
            },
            "token-wide-no": {
                "asset_id": "token-wide-no",
                "market": "condition-wide",
                "bids": [{"price": "0.98", "size": "25"}],
                "asks": [{"price": "0.99", "size": "25"}],
                "last_trade_price": "0.985",
                "tick_size": "0.01",
                "min_order_size": "1",
            },
            "token-balanced-no": {
                "asset_id": "token-balanced-no",
                "market": "condition-balanced",
                "bids": [{"price": "0.48", "size": "25"}],
                "asks": [{"price": "0.52", "size": "25"}],
                "last_trade_price": "0.50",
                "tick_size": "0.01",
                "min_order_size": "1",
            },
        }
        return [books[token_id] for token_id in token_ids]


def test_prepare_strategy_raw_config_bootstraps_market_selection() -> None:
    prepared = prepare_strategy_raw_config(
        {
            "mode": "realtime_paper",
            "universe": {"dataset_id": "automation-market-store", "token_ids": [], "token_mappings": []},
        },
        market_store=FakeMarketStore(),
    )

    assert prepared["universe"]["token_ids"] == ["token-yes"]
    assert prepared["universe"]["token_mappings"][0]["condition_id"] == "condition-1"


def test_prepare_strategy_raw_config_prefers_balanced_bootstrap_market_when_books_exist() -> None:
    prepared = prepare_strategy_raw_config(
        {
            "mode": "realtime_paper",
            "universe": {"dataset_id": "automation-market-store", "token_ids": [], "token_mappings": []},
        },
        market_store=FakeMarketStore(
            [
                FakeMarket(
                    market_id="market-wide",
                    condition_id="condition-wide",
                    yes_token_id="token-wide",
                    no_token_id="token-wide-no",
                    liquidity=5000,
                ),
                FakeMarket(
                    market_id="market-balanced",
                    condition_id="condition-balanced",
                    yes_token_id="token-balanced",
                    no_token_id="token-balanced-no",
                    liquidity=4000,
                ),
            ]
        ),
        clob_client=FakeClobClient(),
    )

    assert prepared["universe"]["token_ids"] == ["token-balanced"]
    assert prepared["universe"]["token_mappings"][0]["condition_id"] == "condition-balanced"


def test_build_bootstrap_market_events_uses_live_book_prices() -> None:
    events = build_bootstrap_market_events(
        {
            "universe": {
                "token_ids": ["token-yes"],
                "token_mappings": [{"token_id": "token-yes", "condition_id": "condition-1"}],
            }
        },
        clob_client=FakeClobClient(),
        now=datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc),
    )

    assert len(events) == 1
    assert events[0].token_id == "token-yes"
    market_data = events[0].payload["by_token"]["token-yes"]
    assert str(market_data["midpoint"]) == "0.45"
    assert str(market_data["last_trade_price"]) == "0.45"


def test_build_bootstrap_market_events_generates_staged_sequence_for_stress_strategy() -> None:
    events = build_bootstrap_market_events(
        {
            "strategy": {
                "stress_profile": "medium",
                "stress_stage_interval_seconds": 20,
            },
            "universe": {
                "token_ids": ["token-yes"],
                "token_mappings": [{"token_id": "token-yes", "condition_id": "condition-1"}],
            },
        },
        clob_client=FakeClobClient(),
        now=datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc),
    )

    assert len(events) == 4
    assert [event.ts.isoformat() for event in events] == [
        "2026-04-22T10:00:00+00:00",
        "2026-04-22T10:00:20+00:00",
        "2026-04-22T10:00:40+00:00",
        "2026-04-22T10:01:00+00:00",
    ]
    assert [event.payload["by_token"]["token-yes"]["bootstrap_stage"] for event in events] == [0, 1, 2, 3]
    book_levels = events[0].payload["by_token"]["token-yes"]["book_levels"]
    assert "bids" in book_levels
    assert "asks" in book_levels
    assert book_levels["asks"][0]["size"] == 250
