from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from polymarket_quant.domain.strategy import (
    ResolvedRunConfig,
    RunManifest,
    RunMode,
    StrategyContextSnapshot,
    StrategyEvent,
    StrategyEventType,
    StrategySignal,
    UniverseSnapshot,
)
from polymarket_quant.strategy.base import BaseStrategy


def instant() -> datetime:
    return datetime(2026, 4, 21, 8, 0, tzinfo=timezone.utc)


def resolved_run_config(**overrides: object) -> ResolvedRunConfig:
    values = {
        "strategy": {"name": "mean-reversion", "params": {"lookback": 20}},
        "universe": {"selector": "top_n", "top_n": 25},
        "sizing": {"mode": "exposure", "max_per_token": "0.05"},
        "execution": {"style": "limit", "post_only": False},
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
        "token_ids": ["token-yes", "token-no"],
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


def context(**overrides: object) -> StrategyContextSnapshot:
    values = {
        "timestamp": instant(),
        "run_mode": RunMode.REPLAY,
        "market_data": {"token_id": "token-yes", "best_bid": "0.44"},
        "features": {"mid_reversion_zscore": "1.2"},
        "portfolio": {"cash": "1000", "positions": {}},
        "recent_fills": [{"fill_id": "fill-1"}],
        "recent_risk_decisions": [{"decision": "ALLOW"}],
        "run_config": resolved_run_config(),
        "time_window": {"start": "2026-04-20T00:00:00Z", "end": "2026-04-21T00:00:00Z"},
    }
    values.update(overrides)
    return StrategyContextSnapshot(**values)


def test_signal_requires_token_and_timestamp() -> None:
    signal = StrategySignal(
        token_id="token-yes",
        target_exposure=Decimal("0.25"),
        ts=instant(),
        reason_code="alpha_up",
        confidence=Decimal("0.8"),
    )

    assert signal.token_id == "token-yes"
    assert signal.target_exposure == Decimal("0.25")
    assert signal.ts == instant()


def test_signal_rejects_missing_targets() -> None:
    with pytest.raises(ValidationError):
        StrategySignal(token_id="token-yes", ts=instant())


def test_resolved_run_config_persists_required_sections() -> None:
    config = resolved_run_config()

    assert config.strategy["name"] == "mean-reversion"
    assert config.universe["selector"] == "top_n"
    assert config.sizing["mode"] == "exposure"
    assert config.execution["style"] == "limit"
    assert config.risk["max_token_position"] == "100"
    assert config.data_sources["market_data"] == "postgres"


def test_universe_snapshot_rejects_blank_token_ids() -> None:
    with pytest.raises(ValidationError):
        universe_snapshot(token_ids=["token-yes", " "])


def test_run_manifest_tracks_required_metadata() -> None:
    manifest = RunManifest(
        run_id="run-001",
        strategy_name="mean-reversion",
        strategy_version="2026.04.21",
        git_commit="abc1234",
        start_time=instant(),
        end_time=instant(),
        mode=RunMode.REPLAY,
        environment="local",
        resolved_config=resolved_run_config(),
        universe_snapshot=universe_snapshot(),
        artifact_files={"manifest": "manifest.json"},
    )

    assert manifest.run_id == "run-001"
    assert manifest.mode == RunMode.REPLAY
    assert manifest.artifact_files["manifest"] == "manifest.json"


def test_strategy_event_requires_non_blank_source() -> None:
    with pytest.raises(ValidationError):
        StrategyEvent(
            event_type=StrategyEventType.MARKET,
            ts=instant(),
            source=" ",
        )


def test_base_strategy_exposes_required_lifecycle_methods() -> None:
    strategy = BaseStrategy()
    snapshot = context()

    assert strategy.on_init(snapshot) == []
    assert strategy.on_event(
        StrategyEvent(
            event_type=StrategyEventType.MARKET,
            ts=instant(),
            token_id="token-yes",
            source="normalized",
        ),
        snapshot,
    ) == []
    assert strategy.on_clock(instant(), snapshot) == []
    assert strategy.on_finish(snapshot) == []
