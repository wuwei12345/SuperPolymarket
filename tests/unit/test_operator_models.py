from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import yaml

from polymarket_quant.domain.operator import (
    GlobalMode,
    LocalRunMode,
    NewOrderBlockState,
    RuntimeStatusSnapshot,
    StrategyRuntimeState,
)
from polymarket_quant.domain.strategy import StrategyEvent, StrategyEventType, StrategySignal
from polymarket_quant.services.operator_runtime_registry import OperatorRuntimeRegistry
from polymarket_quant.services.strategy_cli import StrategyCliService
from polymarket_quant.strategy.base import BaseStrategy


class SilentStrategy(BaseStrategy):
    def on_clock(self, ts: datetime, ctx: object) -> list[StrategySignal]:
        return []


def instant() -> datetime:
    return datetime(2026, 4, 22, 8, 0, tzinfo=timezone.utc)


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
                }
            }
        },
    )


def write_yaml_config(path: Path, *, mode: str) -> None:
    path.write_text(
        yaml.safe_dump(
            {
                "run_id": "run-phase5",
                "environment": "local",
                "mode": mode,
                "step_interval": "1m",
                "strategy": {"name": "phase5_strategy", "version": "0.5.0"},
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
                    "start": "2026-04-22T08:00:00+00:00",
                    "end": "2026-04-22T08:05:00+00:00",
                },
            }
        )
    )


def test_operator_models_distinguish_global_and_local_modes() -> None:
    snapshot = RuntimeStatusSnapshot(
        run_id="run-1",
        strategy_name="s1",
        strategy_version="0.5.0",
        global_mode=GlobalMode.PAPER,
        local_mode=LocalRunMode.REALTIME_PAPER,
        state=StrategyRuntimeState.RUNNING,
    )

    assert snapshot.global_mode == GlobalMode.PAPER
    assert snapshot.local_mode == LocalRunMode.REALTIME_PAPER
    assert snapshot.global_mode.value != snapshot.local_mode.value


def test_runtime_snapshot_tracks_last_heartbeat_and_block_state() -> None:
    snapshot = RuntimeStatusSnapshot(
        run_id="run-2",
        strategy_name="s2",
        strategy_version="0.5.0",
        global_mode=GlobalMode.REPLAY,
        local_mode=LocalRunMode.RESEARCH,
        state=StrategyRuntimeState.BLOCKED,
        new_order_status=NewOrderBlockState.FULLY_BLOCKED,
        last_heartbeat=instant(),
    )

    assert snapshot.last_heartbeat == instant()
    assert snapshot.new_order_status == NewOrderBlockState.FULLY_BLOCKED
    assert snapshot.state == StrategyRuntimeState.BLOCKED


def test_registry_tracks_global_mode_and_run_heartbeat() -> None:
    registry = OperatorRuntimeRegistry()
    registry.set_global_mode(GlobalMode.PAPER)
    registry.start_run(
        run_id="run-3",
        strategy_name="s3",
        strategy_version="0.5.0",
        local_mode=LocalRunMode.REALTIME_PAPER,
        state=StrategyRuntimeState.STARTING,
        heartbeat_at=instant(),
    )

    snapshot = registry.heartbeat(
        "run-3",
        at=datetime(2026, 4, 22, 8, 5, tzinfo=timezone.utc),
        state=StrategyRuntimeState.RUNNING,
        new_order_status=NewOrderBlockState.PARTIALLY_BLOCKED,
        active_positions=2,
        open_orders=1,
    )

    assert registry.get_global_mode() == GlobalMode.PAPER
    assert snapshot.last_heartbeat == datetime(2026, 4, 22, 8, 5, tzinfo=timezone.utc)
    assert snapshot.state == StrategyRuntimeState.RUNNING
    assert snapshot.new_order_status == NewOrderBlockState.PARTIALLY_BLOCKED
    assert snapshot.active_positions == 2
    assert snapshot.open_orders == 1


def test_strategy_cli_publishes_runtime_snapshots(tmp_path: Path) -> None:
    config_path = tmp_path / "phase5.yaml"
    write_yaml_config(config_path, mode="replay")
    registry = OperatorRuntimeRegistry()

    StrategyCliService(
        tmp_path,
        git_commit="deadbeef",
        runtime_registry=registry,
    ).run(
        SilentStrategy(),
        config_path,
        events=[market_event()],
    )

    snapshot = registry.get_run("run-phase5")

    assert snapshot is not None
    assert snapshot.strategy_name == "phase5_strategy"
    assert snapshot.global_mode == GlobalMode.REPLAY
    assert snapshot.local_mode == LocalRunMode.REPLAY
    assert snapshot.state == StrategyRuntimeState.FINISHED
    assert snapshot.last_heartbeat == instant()
