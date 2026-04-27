from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import yaml

from polymarket_quant.domain.market_data import BookLevel, BookSnapshot
from polymarket_quant.domain.strategy import RunMode, StrategyEvent, StrategyEventType, StrategySignal
from polymarket_quant.services.experiment_metrics import ExperimentMetricsService
from polymarket_quant.services.order_risk import MarketConstraints, RiskLimits
from polymarket_quant.services.paper_exchange import PaperExchangeService
from polymarket_quant.services.strategy_cli import StrategyCliService
from polymarket_quant.strategy.base import BaseStrategy
from polymarket_quant.services.fill_engine import FillEngineConfig


class SilentStrategy(BaseStrategy):
    def on_clock(self, ts: datetime, ctx: object) -> list[StrategySignal]:
        return []


class BuyAndHoldStrategy(BaseStrategy):
    def on_event(self, event: StrategyEvent, ctx: object) -> list[StrategySignal]:
        if event.event_type == StrategyEventType.MARKET:
            return [
                StrategySignal(
                    token_id="token-yes",
                    target_position=Decimal("5"),
                    ts=event.ts,
                    reason_code="enter",
                )
            ]
        return []


class RecordingCliService(StrategyCliService):
    def __init__(self, artifact_root: str | Path) -> None:
        super().__init__(artifact_root, git_commit="deadbeef")
        self.called_mode = None

    def run_replay(self, strategy: BaseStrategy, resolved_config: object, *, events: list[StrategyEvent]) -> dict[str, object]:
        self.called_mode = "replay"
        return {
            "signals": [],
            "order_intents": [],
            "orders": [],
            "fills": [],
            "positions": [],
            "cash_ledger": [],
            "pnl_timeline": [],
            "risk_decisions": [],
            "strategy_log": "",
            "framework_log": "",
        }

    def run_realtime_paper(
        self,
        strategy: BaseStrategy,
        resolved_config: object,
        *,
        events: list[StrategyEvent],
        constraints_provider=None,
        limits_provider=None,
        snapshot_provider=None,
        paper_exchange=None,
    ) -> dict[str, object]:
        self.called_mode = "realtime_paper"
        return {
            "signals": [],
            "order_intents": [],
            "orders": [],
            "fills": [],
            "positions": [],
            "cash_ledger": [],
            "pnl_timeline": [],
            "risk_decisions": [],
            "strategy_log": "",
            "framework_log": "",
        }


def instant() -> datetime:
    return datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)


def market_event() -> StrategyEvent:
    return StrategyEvent(
        event_type=StrategyEventType.MARKET,
        ts=instant(),
        token_id="token-yes",
        condition_id="0xcondition",
        source="clob_ws",
        payload={
            "by_token": {
                "token-yes": {
                    "token_id": "token-yes",
                    "condition_id": "0xcondition",
                    "best_bid": Decimal("0.44"),
                    "best_ask": Decimal("0.46"),
                    "midpoint": Decimal("0.45"),
                    "last_trade_price": Decimal("0.45"),
                    "tick_size": Decimal("0.01"),
                    "min_order_size": Decimal("1"),
                }
            }
        },
    )


def snapshot() -> BookSnapshot:
    return BookSnapshot(
        token_id="token-yes",
        condition_id="0xcondition",
        source_ts=instant(),
        received_at=instant(),
        bids=[BookLevel(side="BUY", price=Decimal("0.44"), size=Decimal("10"))],
        asks=[BookLevel(side="SELL", price=Decimal("0.46"), size=Decimal("10"))],
        last_trade_price=Decimal("0.45"),
    )


def constraints() -> MarketConstraints:
    return MarketConstraints(
        token_id="token-yes",
        condition_id="0xcondition",
        tick_size=Decimal("0.01"),
        min_order_size=Decimal("1"),
        best_bid=Decimal("0.44"),
        best_ask=Decimal("0.46"),
        spread=Decimal("0.02"),
    )


def limits() -> RiskLimits:
    return RiskLimits(
        cash_available=Decimal("100"),
        token_position=Decimal("100"),
        max_single_order_notional=Decimal("100"),
        max_market_position=Decimal("100"),
        max_token_position=Decimal("100"),
    )


def write_yaml_config(path: Path, *, mode: str) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "run_id": "run-phase4",
                "environment": "local",
                "mode": mode,
                "step_interval": "1m",
                "strategy": {"name": "phase4_strategy", "version": "0.4.0"},
                "universe": {
                    "dataset_id": "dataset-001",
                    "token_ids": ["token-yes"],
                    "token_mappings": [{"token_id": "token-yes", "condition_id": "0xcondition"}],
                },
                "risk": {
                    "cash_available": "100",
                    "max_single_order_notional": "100",
                    "max_market_position": "100",
                    "max_token_position": "100",
                },
                "execution": {"time_in_force": "GTC"},
                "replay": {
                    "start": "2026-04-21T12:00:00+00:00",
                    "end": "2026-04-21T12:05:00+00:00",
                },
            }
        )
    )


def test_metrics_service_computes_required_run_summary_fields() -> None:
    metrics = ExperimentMetricsService().compute_summary(
        order_intents=[
            {"client_order_id": "o1", "price": Decimal("0.45"), "size": Decimal("10")}
        ],
        orders=[
            {"client_order_id": "o1", "status": "CANCELED"},
            {"client_order_id": "o2", "status": "FILLED"},
        ],
        fills=[
            {
                "client_order_id": "o1",
                "token_id": "token-yes",
                "side": "BUY",
                "price": Decimal("0.46"),
                "size": Decimal("5"),
                "created_at": instant(),
            },
            {
                "client_order_id": "o1",
                "token_id": "token-yes",
                "side": "SELL",
                "price": Decimal("0.48"),
                "size": Decimal("5"),
                "created_at": instant() + timedelta(minutes=10),
            },
        ],
        positions=[
            {"token_id": "token-yes", "quantity": Decimal("5"), "mark_price": Decimal("0.46")}
        ],
        pnl_timeline=[
            {"realized_pnl": Decimal("0"), "unrealized_pnl": Decimal("1"), "total_pnl": Decimal("1")},
            {"realized_pnl": Decimal("2"), "unrealized_pnl": Decimal("0"), "total_pnl": Decimal("2")},
            {"realized_pnl": Decimal("1.5"), "unrealized_pnl": Decimal("0"), "total_pnl": Decimal("1.5")},
        ],
        risk_decisions=[{"decision": "REJECT"}],
        starting_equity=Decimal("100"),
    )

    assert set(metrics) >= {
        "total_return",
        "realized_pnl",
        "unrealized_pnl",
        "turnover",
        "fill_rate",
        "cancel_rate",
        "average_holding_time_seconds",
        "max_drawdown",
        "exposure_peak",
        "reject_count",
        "slippage_notional",
        "slippage_average",
        "slippage_bps",
    }
    assert metrics["fill_rate"] == Decimal("1.044444444444444444444444444")
    assert metrics["max_drawdown"] == Decimal("0.5")
    assert metrics["reject_count"] == 1


def test_metrics_service_derives_realized_pnl_from_fills_without_timeline() -> None:
    metrics = ExperimentMetricsService().compute_summary(
        fills=[
            {
                "client_order_id": "o1",
                "token_id": "token-yes",
                "side": "BUY",
                "price": Decimal("0.50"),
                "size": Decimal("10"),
                "created_at": instant(),
            },
            {
                "client_order_id": "o2",
                "token_id": "token-yes",
                "side": "SELL",
                "price": Decimal("0.55"),
                "size": Decimal("4"),
                "created_at": instant() + timedelta(minutes=1),
            },
            {
                "client_order_id": "o3",
                "token_id": "token-yes",
                "side": "SELL",
                "price": Decimal("0.45"),
                "size": Decimal("6"),
                "created_at": instant() + timedelta(minutes=2),
            },
        ],
        positions=[{"token_id": "token-yes", "quantity": "0", "mark_price": "0.45"}],
        starting_equity=Decimal("100"),
    )

    assert metrics["realized_pnl"] == Decimal("-0.10")
    assert metrics["unrealized_pnl"] == Decimal("0.00")
    assert metrics["total_return"] == Decimal("-0.001")


def test_cli_resolves_yaml_config_and_writes_manifest(tmp_path: Path) -> None:
    config_path = tmp_path / "phase4.yaml"
    write_yaml_config(config_path, mode="replay")

    result = StrategyCliService(tmp_path, git_commit="deadbeef").run(
        SilentStrategy(),
        config_path,
        events=[market_event()],
    )

    manifest_path = result.run_directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())

    assert manifest_path.exists()
    assert result.manifest.mode == RunMode.REPLAY
    assert manifest["resolved_config"]["execution"]["time_in_force"] == "GTC"
    assert manifest["resolved_config"]["execution"]["post_only"] is False
    assert manifest["resolved_config"]["strategy"]["name"] == "phase4_strategy"
    assert manifest["artifact_files"]["strategy_log"] == "strategy.log"


def test_cli_dispatches_to_selected_run_mode(tmp_path: Path) -> None:
    config_path = tmp_path / "phase4-realtime.yaml"
    write_yaml_config(config_path, mode="realtime_paper")

    service = RecordingCliService(tmp_path)
    service.run(BuyAndHoldStrategy(), config_path, events=[market_event()])

    assert service.called_mode == "realtime_paper"


def test_readme_documents_phase4_runtime_scope() -> None:
    readme = Path("README.md").read_text()

    assert "## Phase 4 Strategy Runtime" in readme
    assert "on_init" in readme
    assert "target_exposure" in readme
    assert "manifest.json" in readme
    assert "replay" in readme
    assert "realtime paper" in readme


def test_cli_realtime_paper_writes_metrics_and_artifacts(tmp_path: Path) -> None:
    config_path = tmp_path / "phase4-realtime.yaml"
    write_yaml_config(config_path, mode="realtime_paper")

    result = StrategyCliService(tmp_path, git_commit="deadbeef").run(
        BuyAndHoldStrategy(),
        config_path,
        events=[market_event()],
        constraints_provider=lambda _signal: constraints(),
        limits_provider=lambda _signal: limits(),
        snapshot_provider=lambda _signal: snapshot(),
        paper_exchange=PaperExchangeService(
            fill_config=FillEngineConfig(submit_latency_ms=0, cancel_latency_ms=0)
        ),
    )

    assert (result.run_directory / "signals.parquet").exists()
    assert (result.run_directory / "order_intents.parquet").exists()
    assert (result.run_directory / "fills.parquet").exists()
    assert result.metrics_summary["fill_rate"] > 0


def test_snapshot_provider_uses_explicit_book_levels_from_market_payload(tmp_path: Path) -> None:
    service = StrategyCliService(tmp_path, git_commit="deadbeef")
    config_path = tmp_path / "phase4-realtime.yaml"
    write_yaml_config(config_path, mode="realtime_paper")
    raw_config = service.load_config(config_path)
    resolved_config = service.resolve_config(raw_config, strategy_name="phase4_strategy")
    event = StrategyEvent(
        event_type=StrategyEventType.MARKET,
        ts=instant(),
        token_id="token-yes",
        condition_id="0xcondition",
        source="clob_ws",
        payload={
            "by_token": {
                "token-yes": {
                    "token_id": "token-yes",
                    "condition_id": "0xcondition",
                    "best_bid": Decimal("0.44"),
                    "best_ask": Decimal("0.46"),
                    "book_levels": {
                        "bids": [{"price": Decimal("0.44"), "size": Decimal("25")}],
                        "asks": [{"price": Decimal("0.46"), "size": Decimal("30")}],
                    },
                }
            }
        },
    )
    runtime = service._runtime(SilentStrategy(), resolved_config, [event])
    runtime.on_event(event)

    result = service._snapshot_from_runtime(
        StrategySignal(
            token_id="token-yes",
            target_position=Decimal("5"),
            ts=instant(),
            reason_code="test_snapshot",
        ),
        runtime,
    )

    assert result is not None
    assert result.bids[0].size == Decimal("25")
    assert result.asks[0].size == Decimal("30")
