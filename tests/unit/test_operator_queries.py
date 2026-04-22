from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from polymarket_quant.domain.operator import (
    AlertSummary,
    ConnectionComponent,
    ConnectionState,
    ConnectionStatus,
    GlobalMode,
    LocalRunMode,
    NewOrderBlockState,
    StrategyRuntimeState,
)
from polymarket_quant.domain.strategy import (
    ResolvedRunConfig,
    RunManifest,
    RunMode,
    UniverseSnapshot,
)
from polymarket_quant.services.operator_queries import OperatorFilters, OperatorQueryService
from polymarket_quant.services.operator_runtime_registry import OperatorRuntimeRegistry
from polymarket_quant.services.run_artifacts import RunArtifactBundleWriter


class FakeMarketDataStore:
    def __init__(self, latest_state: list[dict[str, Any]]) -> None:
        self.latest_state = latest_state

    def fetch_latest_state(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.latest_state[:limit]


def instant(day_offset: int = 0) -> datetime:
    return datetime(2026, 4, 22 + day_offset, 8, 0, tzinfo=timezone.utc)


def resolved_run_config(mode: RunMode) -> ResolvedRunConfig:
    return ResolvedRunConfig(
        strategy={"name": "strategy", "version": "dev"},
        universe={"selector": "top_n"},
        sizing={"mode": "exposure"},
        execution={"style": "limit"},
        risk={"cash_available": "1000"},
        data_sources={"artifacts": "local"},
        mode=mode,
        replay={},
        realtime={},
    )


def universe_snapshot(
    *,
    market_id: str,
    event_id: str,
    token_id: str,
    day_offset: int,
) -> UniverseSnapshot:
    return UniverseSnapshot(
        dataset_id=f"dataset-{market_id}",
        selection={"active": True},
        token_ids=[token_id],
        token_mappings=[
            {
                "market_id": market_id,
                "event_id": event_id,
                "token_id": token_id,
                "condition_id": f"condition-{event_id}",
            }
        ],
        window_start=instant(day_offset),
        window_end=instant(day_offset) + timedelta(hours=1),
        includes_gap_fill=(day_offset % 2 == 0),
    )


def manifest(
    *,
    run_id: str,
    strategy_name: str,
    mode: RunMode,
    market_id: str,
    event_id: str,
    token_id: str,
    day_offset: int,
    metrics_summary: dict[str, Any],
) -> RunManifest:
    return RunManifest(
        run_id=run_id,
        strategy_name=strategy_name,
        strategy_version="1.0.0",
        git_commit="deadbeef",
        start_time=instant(day_offset),
        end_time=instant(day_offset) + timedelta(hours=1),
        mode=mode,
        environment="local",
        resolved_config=resolved_run_config(mode),
        universe_snapshot=universe_snapshot(
            market_id=market_id,
            event_id=event_id,
            token_id=token_id,
            day_offset=day_offset,
        ),
        metrics_summary=metrics_summary,
    )


def write_run_bundle(
    artifact_root: Path,
    *,
    manifest_obj: RunManifest,
    position_quantity: str,
    order_status: str,
    risk_decision: str,
) -> None:
    writer = RunArtifactBundleWriter(artifact_root)
    writer.write_bundle(
        manifest_obj,
        orders=[
            {
                "client_order_id": f"{manifest_obj.run_id}-order",
                "token_id": manifest_obj.universe_snapshot.token_ids[0],
                "status": order_status,
            }
        ],
        positions=[
            {
                "strategy_id": manifest_obj.strategy_name,
                "token_id": manifest_obj.universe_snapshot.token_ids[0],
                "quantity": position_quantity,
                "mark_price": "0.52",
            }
        ],
        pnl_timeline=[
            {
                "strategy_id": manifest_obj.strategy_name,
                "token_id": manifest_obj.universe_snapshot.token_ids[0],
                "realized_pnl": str(manifest_obj.metrics_summary["realized_pnl"]),
                "unrealized_pnl": str(manifest_obj.metrics_summary["unrealized_pnl"]),
                "total_pnl": str(
                    Decimal(str(manifest_obj.metrics_summary["realized_pnl"]))
                    + Decimal(str(manifest_obj.metrics_summary["unrealized_pnl"]))
                ),
            }
        ],
        risk_decisions=[
            {
                "client_order_id": f"{manifest_obj.run_id}-order",
                "token_id": manifest_obj.universe_snapshot.token_ids[0],
                "decision": risk_decision,
                "warnings": ["spread_warning"],
                "created_at": manifest_obj.end_time,
            }
        ],
        strategy_log="strategy log\n",
        framework_log="framework log\n",
    )


def registry_with_runs() -> OperatorRuntimeRegistry:
    registry = OperatorRuntimeRegistry(global_mode=GlobalMode.PAPER)
    registry.start_run(
        run_id="run-a",
        strategy_name="mean-reversion",
        strategy_version="1.0.0",
        local_mode=LocalRunMode.REPLAY,
        heartbeat_at=instant(0),
    )
    registry.heartbeat(
        "run-a",
        at=instant(0) + timedelta(minutes=15),
        state=StrategyRuntimeState.RUNNING,
        new_order_status=NewOrderBlockState.ALLOWED,
        active_positions=1,
        open_orders=2,
        latest_pnl=12.5,
        latest_drawdown=1.2,
    )
    registry._runs["run-a"] = registry._runs["run-a"].model_copy(
        update={"alert_summary": AlertSummary(Warning=1, Critical=1)}
    )

    registry.start_run(
        run_id="run-b",
        strategy_name="momentum",
        strategy_version="1.0.0",
        local_mode=LocalRunMode.REALTIME_PAPER,
        heartbeat_at=instant(1),
    )
    registry.heartbeat(
        "run-b",
        at=instant(1) + timedelta(minutes=20),
        state=StrategyRuntimeState.BLOCKED,
        new_order_status=NewOrderBlockState.PARTIALLY_BLOCKED,
        active_positions=2,
        open_orders=1,
        latest_pnl=-3.5,
        latest_drawdown=2.4,
    )
    registry._runs["run-b"] = registry._runs["run-b"].model_copy(
        update={"alert_summary": AlertSummary(Critical=2)}
    )
    return registry


def test_operator_queries_group_by_strategy_market_event_and_time_window(
    tmp_path: Path,
) -> None:
    write_run_bundle(
        tmp_path,
        manifest_obj=manifest(
            run_id="run-a",
            strategy_name="mean-reversion",
            mode=RunMode.REPLAY,
            market_id="market-1",
            event_id="event-1",
            token_id="token-yes",
            day_offset=0,
            metrics_summary={
                "realized_pnl": Decimal("10"),
                "unrealized_pnl": Decimal("2"),
                "turnover": Decimal("25"),
                "max_drawdown": Decimal("1"),
                "exposure_peak": Decimal("6"),
            },
        ),
        position_quantity="5",
        order_status="OPEN",
        risk_decision="WARN",
    )
    write_run_bundle(
        tmp_path,
        manifest_obj=manifest(
            run_id="run-b",
            strategy_name="momentum",
            mode=RunMode.REALTIME_PAPER,
            market_id="market-2",
            event_id="event-2",
            token_id="token-no",
            day_offset=1,
            metrics_summary={
                "realized_pnl": Decimal("-4"),
                "unrealized_pnl": Decimal("0"),
                "turnover": Decimal("12"),
                "max_drawdown": Decimal("3"),
                "exposure_peak": Decimal("4"),
            },
        ),
        position_quantity="2",
        order_status="PARTIALLY_FILLED",
        risk_decision="REJECT",
    )

    service = OperatorQueryService(
        tmp_path,
        runtime_registry=registry_with_runs(),
    )

    strategy_rows = service.overview(group_by="strategy")
    market_rows = service.overview(group_by="market")
    event_rows = service.overview(group_by="event")
    time_window_rows = service.overview(group_by="time_window")

    assert {row["group_value"] for row in strategy_rows} == {
        "mean-reversion",
        "momentum",
    }
    assert {row["group_value"] for row in market_rows} == {"market-1", "market-2"}
    assert {row["group_value"] for row in event_rows} == {"event-1", "event-2"}
    assert len(time_window_rows) == 2
    assert all("win_rate" in row for row in strategy_rows + market_rows + event_rows)


def test_operator_queries_merge_run_metrics_positions_orders_and_alerts(
    tmp_path: Path,
) -> None:
    write_run_bundle(
        tmp_path,
        manifest_obj=manifest(
            run_id="run-a",
            strategy_name="mean-reversion",
            mode=RunMode.REPLAY,
            market_id="market-1",
            event_id="event-1",
            token_id="token-yes",
            day_offset=0,
            metrics_summary={
                "realized_pnl": Decimal("10"),
                "unrealized_pnl": Decimal("2"),
                "turnover": Decimal("25"),
                "max_drawdown": Decimal("1"),
                "exposure_peak": Decimal("6"),
            },
        ),
        position_quantity="5",
        order_status="OPEN",
        risk_decision="WARN",
    )
    service = OperatorQueryService(
        tmp_path,
        runtime_registry=registry_with_runs(),
        market_data_store=FakeMarketDataStore(
            [
                {
                    "market_id": "market-1",
                    "token_id": "token-yes",
                    "received_at": instant(0).isoformat(),
                    "gap_fill": True,
                }
            ]
        ),
        connections_provider=lambda: [
            ConnectionState(
                component=ConnectionComponent.DB,
                status=ConnectionStatus.HEALTHY,
                updated_at=instant(0),
            )
        ],
    )

    filters = OperatorFilters(strategy="mean-reversion")
    overview = service.overview(group_by="strategy", filters=filters)[0]
    detail = service.positions_orders(filters)
    pnl = service.pnl_exposure(filters)[0]
    timeline = service.alerts_timeline(filters)
    status_band = service.status_band(filters)

    assert overview["active_positions"] == 1
    assert overview["open_orders"] == 2
    assert overview["latest_pnl"] == Decimal("12.5")
    assert overview["alerts"] == 2
    assert overview["last_heartbeat"] == instant(0) + timedelta(minutes=15)

    assert detail["positions"][0]["token_id"] == "token-yes"
    assert detail["orders"][0]["status"] == "OPEN"
    assert pnl["turnover"] == Decimal("25")
    assert pnl["exposure_peak"] == Decimal("6")
    assert any("last_heartbeat" in row["message"] for row in timeline)
    assert any("risk decision=WARN" in row["message"] for row in timeline)
    assert status_band["global_mode"] == GlobalMode.PAPER


def test_operator_queries_list_runs_and_artifacts_from_manifest_bundle(
    tmp_path: Path,
) -> None:
    write_run_bundle(
        tmp_path,
        manifest_obj=manifest(
            run_id="run-a",
            strategy_name="mean-reversion",
            mode=RunMode.REPLAY,
            market_id="market-1",
            event_id="event-1",
            token_id="token-yes",
            day_offset=0,
            metrics_summary={
                "realized_pnl": Decimal("10"),
                "unrealized_pnl": Decimal("2"),
                "turnover": Decimal("25"),
                "max_drawdown": Decimal("1"),
                "exposure_peak": Decimal("6"),
            },
        ),
        position_quantity="5",
        order_status="OPEN",
        risk_decision="WARN",
    )

    service = OperatorQueryService(tmp_path, runtime_registry=registry_with_runs())
    rows = service.runs_artifacts()

    assert len(rows) == 1
    assert rows[0]["run_id"] == "run-a"
    assert rows[0]["artifact_files"]["orders"] == "orders.parquet"
    assert rows[0]["artifact_files"]["positions"] == "positions.parquet"
    assert rows[0]["artifact_files"]["risk_decisions"] == "risk_decisions.parquet"
    assert rows[0]["run_directory"] == str(tmp_path / "run-a")
