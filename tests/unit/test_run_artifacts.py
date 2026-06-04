from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pandas as pd

from polymarket_quant.domain.simulation import (
    OrderIntent,
    OrderSide,
    RiskCheckResult,
    RiskDecision,
    RiskDecisionType,
)
from polymarket_quant.domain.strategy import (
    ResolvedRunConfig,
    RunManifest,
    RunMode,
    StrategySignal,
    UniverseSnapshot,
)
from polymarket_quant.services.run_artifacts import RunArtifactBundleWriter


def instant() -> datetime:
    return datetime(2026, 4, 21, 8, 0, tzinfo=timezone.utc)


def resolved_run_config(**overrides: object) -> ResolvedRunConfig:
    values = {
        "strategy": {"name": "mean-reversion", "params": {"lookback": 20}},
        "universe": {"selector": "top_n", "top_n": 25},
        "sizing": {"mode": "exposure", "max_per_token": "0.05"},
        "execution": {"style": "limit"},
        "risk": {"max_token_position": "100"},
        "data_sources": {"market_data": "postgres", "artifacts": "local"},
        "mode": RunMode.REPLAY,
        "replay": {"window_start": "2026-04-20T00:00:00Z"},
        "realtime": {},
        "step_interval": "1m",
    }
    values.update(overrides)
    return ResolvedRunConfig(**values)


def universe_snapshot(**overrides: object) -> UniverseSnapshot:
    values = {
        "dataset_id": "dataset-001",
        "selection": {"active": True, "accepting_orders": True},
        "token_ids": ["token-yes"],
        "token_mappings": [
            {
                "market_id": "market-1",
                "condition_id": "0xcondition",
                "yes_token_id": "token-yes",
                "no_token_id": "token-no",
            }
        ],
        "window_start": instant(),
        "window_end": instant(),
        "includes_gap_fill": True,
    }
    values.update(overrides)
    return UniverseSnapshot(**values)


def manifest(**overrides: object) -> RunManifest:
    values = {
        "run_id": "run-001",
        "strategy_name": "mean-reversion",
        "strategy_version": "2026.04.21",
        "git_commit": "abc1234",
        "start_time": instant(),
        "end_time": instant(),
        "mode": RunMode.REPLAY,
        "environment": "local",
        "resolved_config": resolved_run_config(),
        "universe_snapshot": universe_snapshot(),
    }
    values.update(overrides)
    return RunManifest(**values)


def order_intent(**overrides: object) -> OrderIntent:
    values = {
        "client_order_id": "order-1",
        "strategy_id": "strategy-a",
        "token_id": "token-yes",
        "condition_id": "0xcondition",
        "side": OrderSide.BUY,
        "price": Decimal("0.45"),
        "size": Decimal("10"),
        "created_at": instant(),
    }
    values.update(overrides)
    return OrderIntent(**values)


def test_writer_creates_manifest_and_required_artifact_files(tmp_path: Path) -> None:
    writer = RunArtifactBundleWriter(tmp_path)

    updated_manifest = writer.write_bundle(
        manifest(),
        signals=[
            StrategySignal(
                token_id="token-yes",
                target_exposure=Decimal("0.25"),
                ts=instant(),
                reason_code="alpha_up",
            )
        ],
        order_intents=[order_intent()],
        positions=[{"token_id": "token-yes", "quantity": "10"}],
        strategy_log="signal emitted\n",
        framework_log="runtime started\n",
    )

    run_dir = tmp_path / "run-001"
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "signals.parquet").exists()
    assert (run_dir / "order_intents.parquet").exists()
    assert (run_dir / "positions.parquet").exists()
    assert (run_dir / "strategy.log").exists()
    assert (run_dir / "framework.log").exists()
    assert updated_manifest.artifact_files["signals"] == "signals.parquet"

    signal_frame = pd.read_parquet(run_dir / "signals.parquet")
    assert signal_frame.loc[0, "token_id"] == "token-yes"


def test_manifest_persists_resolved_config_and_data_scope(tmp_path: Path) -> None:
    writer = RunArtifactBundleWriter(tmp_path)

    writer.write_bundle(
        manifest(
            resolved_config=resolved_run_config(
                strategy={"name": "mean-reversion", "params": {"lookback": 20, "z": 1.5}}
            ),
            universe_snapshot=universe_snapshot(
                selection={"active": True, "top_n": 25},
                includes_gap_fill=True,
            ),
        ),
        fills=[{"fill_id": "fill-1", "price": "0.45"}],
        strategy_log="done\n",
        framework_log="done\n",
    )

    saved_manifest = json.loads((tmp_path / "run-001" / "manifest.json").read_text())
    assert saved_manifest["resolved_config"]["strategy"]["params"]["z"] == 1.5
    assert saved_manifest["universe_snapshot"]["selection"]["top_n"] == 25
    assert saved_manifest["universe_snapshot"]["includes_gap_fill"] is True
    assert saved_manifest["artifact_files"]["fills"] == "fills.parquet"


def test_writer_removes_stale_artifacts_when_later_run_has_no_rows(tmp_path: Path) -> None:
    writer = RunArtifactBundleWriter(tmp_path)

    writer.write_bundle(
        manifest(),
        fills=[{"fill_id": "fill-1", "price": "0.45"}],
        strategy_log="done\n",
        framework_log="done\n",
    )
    assert (tmp_path / "run-001" / "fills.parquet").exists()

    updated_manifest = writer.write_bundle(
        manifest(),
        strategy_log="done\n",
        framework_log="done\n",
    )

    assert not (tmp_path / "run-001" / "fills.parquet").exists()
    assert "fills" not in updated_manifest.artifact_files


def test_writer_sanitizes_empty_struct_fields_for_parquet(tmp_path: Path) -> None:
    writer = RunArtifactBundleWriter(tmp_path)

    writer.write_bundle(
        manifest(),
        risk_decisions=[
            RiskDecision(
                decision=RiskDecisionType.WARN,
                client_order_id="order-1",
                token_id="token-yes",
                condition_id="0xcondition",
                checks=[
                    RiskCheckResult(
                        code="spread",
                        passed=True,
                        severity="warning",
                        message="spread ok",
                        details={},
                    )
                ],
                warnings=["spread ok"],
            )
        ],
        strategy_log="done\n",
        framework_log="done\n",
    )

    risk_frame = pd.read_parquet(tmp_path / "run-001" / "risk_decisions.parquet")
    assert risk_frame.loc[0, "client_order_id"] == "order-1"
