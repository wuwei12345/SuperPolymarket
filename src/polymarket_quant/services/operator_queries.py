from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from polymarket_quant.domain.operator import (
    ConnectionState,
    GlobalMode,
    NewOrderBlockState,
    RuntimeStatusSnapshot,
    StrategyRuntimeState,
)
from polymarket_quant.domain.strategy import RunManifest
from polymarket_quant.services.operator_runtime_registry import OperatorRuntimeRegistry


class SimulationStoreReader(Protocol):
    def fetch_positions(self, strategy_id: str | None = None) -> list[dict[str, Any]]: ...

    def fetch_pnl(self, strategy_id: str | None = None) -> list[dict[str, Any]]: ...


class MarketDataStoreReader(Protocol):
    def fetch_latest_state(self, limit: int = 100) -> list[dict[str, Any]]: ...


class OperatorQueryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OperatorFilters(OperatorQueryModel):
    strategy: str | None = None
    market: str | None = None
    event: str | None = None
    token: str | None = None
    mode: str | None = None
    severity: str | None = None
    status: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None


class OperatorQueryService:
    def __init__(
        self,
        artifact_root: str | Path,
        *,
        runtime_registry: OperatorRuntimeRegistry | None = None,
        simulation_store: SimulationStoreReader | None = None,
        market_data_store: MarketDataStoreReader | None = None,
        connections_provider: Callable[[], list[ConnectionState]] | None = None,
    ) -> None:
        self.artifact_root = Path(artifact_root)
        self.runtime_registry = runtime_registry
        self.simulation_store = simulation_store
        self.market_data_store = market_data_store
        self.connections_provider = connections_provider or (lambda: [])
        self._artifact_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def status_band(self, filters: OperatorFilters | None = None) -> dict[str, Any]:
        filters = filters or OperatorFilters()
        runs = self._run_contexts(filters)
        snapshots = [run["snapshot"] for run in runs if run["snapshot"] is not None]
        fallback_rows = [] if snapshots else runs
        latest_market = self._latest_market_state()
        last_heartbeat = max(
            (snapshot.last_heartbeat for snapshot in snapshots),
            default=None,
        )
        if last_heartbeat is None:
            last_heartbeat = max(
                (
                    row.get("last_heartbeat")
                    for row in fallback_rows
                    if row.get("last_heartbeat") is not None
                ),
                default=None,
            )
        last_market_update = max(
            (_parse_timestamp(row.get("received_at")) for row in latest_market),
            default=None,
        )
        last_updated = max(
            [value for value in (last_heartbeat, last_market_update) if value is not None],
            default=None,
        )
        return {
            "global_mode": self._global_mode(fallback_rows),
            "connections": self.connections_provider(),
            "strategy_summary": _strategy_state_summary(snapshots)
            if snapshots
            else _strategy_state_summary_from_rows(fallback_rows),
            "new_order_status": _worst_block_state(
                [snapshot.new_order_status for snapshot in snapshots]
                or [
                    NewOrderBlockState(str(row["new_order_status"]))
                    for row in fallback_rows
                ]
            ),
            "high_priority_alerts": sum(
                snapshot.alert_summary.Critical for snapshot in snapshots
            )
            if snapshots
            else sum(int(row.get("alerts", 0)) for row in fallback_rows),
            "last_updated": last_updated,
        }

    def overview(
        self,
        *,
        group_by: str = "strategy",
        filters: OperatorFilters | None = None,
    ) -> list[dict[str, Any]]:
        filters = filters or OperatorFilters()
        rows = self._run_contexts(filters)
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            groups[self._group_value(row, group_by)].append(row)
        return [
            self._aggregate_group(group_by, group_value, grouped_rows)
            for group_value, grouped_rows in sorted(groups.items())
        ]

    def positions_orders(
        self, filters: OperatorFilters | None = None
    ) -> dict[str, list[dict[str, Any]]]:
        filters = filters or OperatorFilters()
        runs = self._selected_manifests(filters)
        positions: list[dict[str, Any]] = []
        orders: list[dict[str, Any]] = []
        for manifest in runs:
            run_context = self._manifest_context(manifest)
            for position in self._load_artifact_rows(manifest, "positions"):
                if _matches_token(position, filters.token):
                    positions.append({**run_context, **position})
            for order in self._load_artifact_rows(manifest, "orders"):
                if _matches_token(order, filters.token):
                    orders.append({**run_context, **order})
        if not positions and self.simulation_store is not None:
            positions.extend(self.simulation_store.fetch_positions())
        return {"positions": positions, "orders": orders}

    def pnl_exposure(self, filters: OperatorFilters | None = None) -> list[dict[str, Any]]:
        filters = filters or OperatorFilters()
        rows = [self._pnl_row(manifest) for manifest in self._selected_manifests(filters)]
        if not rows and self.simulation_store is not None:
            rows.extend(self.simulation_store.fetch_pnl())
        return rows

    def pnl_exposure_for_run_ids(self, run_ids: list[str]) -> list[dict[str, Any]]:
        run_id_set = set(run_ids)
        return [
            self._pnl_row(manifest)
            for manifest in self._load_manifests()
            if manifest.run_id in run_id_set
        ]

    def alerts_timeline(
        self, filters: OperatorFilters | None = None
    ) -> list[dict[str, Any]]:
        filters = filters or OperatorFilters()
        timeline: list[dict[str, Any]] = []
        for row in self._run_contexts(filters):
            snapshot: RuntimeStatusSnapshot | None = row["snapshot"]
            if snapshot is not None:
                timeline.append(
                    {
                        "ts": snapshot.last_heartbeat,
                        "severity": _severity_for_snapshot(snapshot),
                        "strategy": row["strategy"],
                        "run_id": row["run_id"],
                        "message": (
                            f"state={snapshot.state.value} "
                            f"new_order_status={snapshot.new_order_status.value} "
                            f"last_heartbeat={snapshot.last_heartbeat.isoformat()}"
                        ),
                    }
                )
            manifest = row["manifest"]
            for decision in self._load_artifact_rows(manifest, "risk_decisions"):
                severity = _severity_for_risk_decision(decision)
                if filters.severity and severity != filters.severity:
                    continue
                timeline.append(
                    {
                        "ts": _parse_timestamp(decision.get("created_at")),
                        "severity": severity,
                        "strategy": manifest.strategy_name,
                        "run_id": manifest.run_id,
                        "message": (
                            f"risk decision={decision.get('decision')} "
                            f"warnings={decision.get('warnings', [])}"
                        ),
                    }
                )
        for market_row in self._latest_market_state():
            if filters.token and str(market_row.get("token_id")) != filters.token:
                continue
            if filters.market and str(market_row.get("market_id")) != filters.market:
                continue
            severity = "Warning" if market_row.get("gap_fill") else "Info"
            if filters.severity and severity != filters.severity:
                continue
            timeline.append(
                {
                    "ts": _parse_timestamp(market_row.get("received_at")),
                    "severity": severity,
                    "strategy": None,
                    "run_id": None,
                    "message": (
                        f"market={market_row.get('market_id')} token={market_row.get('token_id')} "
                        f"gap_fill={market_row.get('gap_fill', False)}"
                    ),
                }
            )
        return sorted(
            timeline,
            key=lambda row: row["ts"] or datetime.min,
            reverse=True,
        )

    def alerts_timeline_for_run_ids(self, run_ids: list[str]) -> list[dict[str, Any]]:
        run_id_set = set(run_ids)
        timeline: list[dict[str, Any]] = []
        snapshots = self._runtime_snapshots()
        for manifest in self._load_manifests():
            if manifest.run_id not in run_id_set:
                continue
            snapshot = snapshots.get(manifest.run_id)
            if snapshot is not None:
                timeline.append(
                    {
                        "ts": snapshot.last_heartbeat,
                        "severity": _severity_for_snapshot(snapshot),
                        "strategy": manifest.strategy_name,
                        "run_id": manifest.run_id,
                        "message": (
                            f"state={snapshot.state.value} "
                            f"new_order_status={snapshot.new_order_status.value} "
                            f"last_heartbeat={snapshot.last_heartbeat.isoformat()}"
                        ),
                    }
                )
            for decision in self._load_artifact_rows(manifest, "risk_decisions"):
                timeline.append(
                    {
                        "ts": _parse_timestamp(decision.get("created_at")),
                        "severity": _severity_for_risk_decision(decision),
                        "strategy": manifest.strategy_name,
                        "run_id": manifest.run_id,
                        "message": (
                            f"risk decision={decision.get('decision')} "
                            f"warnings={decision.get('warnings', [])}"
                        ),
                    }
                )
        return sorted(
            timeline,
            key=lambda row: row["ts"] or datetime.min,
            reverse=True,
        )

    def runs_artifacts(
        self, filters: OperatorFilters | None = None
    ) -> list[dict[str, Any]]:
        filters = filters or OperatorFilters()
        rows: list[dict[str, Any]] = []
        for manifest in self._selected_manifests(filters):
            rows.append(
                {
                    **self._manifest_context(manifest),
                    "artifact_files": manifest.artifact_files,
                    "run_directory": str(self.artifact_root / manifest.run_id),
                }
            )
        return rows

    def runs_artifacts_for_run_ids(self, run_ids: list[str]) -> list[dict[str, Any]]:
        run_id_set = set(run_ids)
        return [
            {
                **self._manifest_context(manifest),
                "artifact_files": manifest.artifact_files,
                "run_directory": str(self.artifact_root / manifest.run_id),
            }
            for manifest in self._load_manifests()
            if manifest.run_id in run_id_set
        ]

    def _run_contexts(self, filters: OperatorFilters) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        snapshots = self._runtime_snapshots()
        for manifest in self._selected_manifests(filters):
            snapshot = snapshots.get(manifest.run_id)
            contexts = self._expanded_run_contexts(manifest, snapshot)
            for context in contexts:
                if _matches_filters(context, filters):
                    rows.append(context)
        return rows

    def _selected_manifests(self, filters: OperatorFilters) -> list[RunManifest]:
        manifests = []
        for manifest in self._load_manifests():
            context = self._manifest_context(manifest)
            if _matches_manifest_filters(context, manifest, filters):
                manifests.append(manifest)
        return manifests

    def _load_manifests(self) -> list[RunManifest]:
        manifests: list[RunManifest] = []
        if not self.artifact_root.exists():
            return manifests
        for manifest_path in sorted(self.artifact_root.glob("*/manifest.json")):
            payload = json.loads(manifest_path.read_text())
            manifests.append(RunManifest.model_validate(payload))
        return manifests

    def _load_artifact_rows(
        self,
        manifest: RunManifest,
        artifact_name: str,
    ) -> list[dict[str, Any]]:
        cache_key = (manifest.run_id, artifact_name)
        if cache_key in self._artifact_cache:
            return self._artifact_cache[cache_key]
        file_name = manifest.artifact_files.get(artifact_name)
        if not file_name:
            self._artifact_cache[cache_key] = []
            return []
        path = self.artifact_root / manifest.run_id / file_name
        if not path.exists():
            self._artifact_cache[cache_key] = []
            return []
        rows = pd.read_parquet(path).to_dict(orient="records")
        self._artifact_cache[cache_key] = rows
        return rows

    def _expanded_run_contexts(
        self,
        manifest: RunManifest,
        snapshot: RuntimeStatusSnapshot | None,
    ) -> list[dict[str, Any]]:
        token_mappings = manifest.universe_snapshot.token_mappings or [{}]
        rows: list[dict[str, Any]] = []
        for mapping in token_mappings:
            metrics = manifest.metrics_summary
            rows.append(
                {
                    "manifest": manifest,
                    "snapshot": snapshot,
                    "run_id": manifest.run_id,
                    "strategy": manifest.strategy_name,
                    "strategy_name": manifest.strategy_name,
                    "market": mapping.get("market_id") or mapping.get("market"),
                    "event": mapping.get("event_id")
                    or mapping.get("condition_id")
                    or mapping.get("question"),
                    "token": mapping.get("token_id")
                    or mapping.get("yes_token_id")
                    or mapping.get("no_token_id"),
                    "mode": manifest.mode.value,
                    "state": (snapshot.state.value if snapshot else StrategyRuntimeState.FINISHED.value),
                    "active_positions": (
                        snapshot.active_positions if snapshot else 0
                    ),
                    "open_orders": snapshot.open_orders if snapshot else 0,
                    "latest_pnl": (
                        snapshot.latest_pnl
                        if snapshot
                        else float(
                            _as_decimal(metrics.get("realized_pnl"))
                            + _as_decimal(metrics.get("unrealized_pnl"))
                        )
                    ),
                    "latest_drawdown": (
                        snapshot.latest_drawdown
                        if snapshot
                        else float(_as_decimal(metrics.get("max_drawdown")))
                    ),
                    "alerts": (
                        snapshot.alert_summary.Info
                        + snapshot.alert_summary.Warning
                        + snapshot.alert_summary.Critical
                        if snapshot
                        else 0
                    ),
                    "new_order_status": (
                        snapshot.new_order_status.value
                        if snapshot
                        else NewOrderBlockState.ALLOWED.value
                    ),
                    "last_heartbeat": snapshot.last_heartbeat if snapshot else manifest.end_time,
                    "turnover": _as_decimal(metrics.get("turnover")),
                    "max_drawdown": _as_decimal(metrics.get("max_drawdown")),
                    "exposure_peak": _as_decimal(metrics.get("exposure_peak")),
                    "win_rate": Decimal("1")
                    if _as_decimal(metrics.get("realized_pnl"))
                    + _as_decimal(metrics.get("unrealized_pnl"))
                    > 0
                    else Decimal("0"),
                    "time_window": _time_window_label(manifest),
                }
            )
        return rows

    def _aggregate_group(
        self,
        group_by: str,
        group_value: str,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]] | dict[str, Any]:
        last_heartbeat = max(
            (row["last_heartbeat"] for row in rows if row["last_heartbeat"] is not None),
            default=None,
        )
        new_order_status = _worst_block_state(
            [NewOrderBlockState(row["new_order_status"]) for row in rows]
        )
        state = _aggregate_state(
            [StrategyRuntimeState(str(row["state"])) for row in rows]
        )
        return {
            "group_by": group_by,
            "group_value": group_value,
            "strategy_name": group_value if group_by == "strategy" else None,
            "market": group_value if group_by == "market" else None,
            "event": group_value if group_by == "event" else None,
            "time_window": group_value if group_by == "time_window" else None,
            "run_count": len({row["run_id"] for row in rows}),
            "mode": ",".join(sorted({str(row["mode"]) for row in rows})),
            "state": state.value,
            "active_positions": sum(int(row["active_positions"]) for row in rows),
            "open_orders": sum(int(row["open_orders"]) for row in rows),
            "latest_pnl": sum(Decimal(str(row["latest_pnl"])) for row in rows),
            "latest_drawdown": max(
                (Decimal(str(row["latest_drawdown"])) for row in rows),
                default=Decimal("0"),
            ),
            "alerts": sum(int(row["alerts"]) for row in rows),
            "new_order_status": new_order_status.value,
            "last_heartbeat": last_heartbeat,
            "turnover": sum(Decimal(str(row["turnover"])) for row in rows),
            "exposure_peak": max(
                (Decimal(str(row["exposure_peak"])) for row in rows),
                default=Decimal("0"),
            ),
            "win_rate": _average_decimal(
                [Decimal(str(row["win_rate"])) for row in rows]
            ),
        }

    def _group_value(self, row: dict[str, Any], group_by: str) -> str:
        if group_by == "strategy":
            return str(row["strategy"])
        if group_by == "market":
            return str(row["market"] or "unknown-market")
        if group_by == "event":
            return str(row["event"] or "unknown-event")
        if group_by == "time_window":
            return str(row["time_window"])
        raise ValueError("group_by must be strategy, market, event, or time_window")

    def _runtime_snapshots(self) -> dict[str, RuntimeStatusSnapshot]:
        if self.runtime_registry is None:
            return {}
        return {snapshot.run_id: snapshot for snapshot in self.runtime_registry.list_runs()}

    def _global_mode(self, fallback_rows: list[dict[str, Any]] | None = None) -> GlobalMode:
        if self.runtime_registry is None:
            if fallback_rows:
                modes = {str(row.get("mode")) for row in fallback_rows}
                if "realtime_paper" in modes or "paper" in modes:
                    return GlobalMode.PAPER
                if "replay" in modes:
                    return GlobalMode.REPLAY
            return GlobalMode.LIVE_DISABLED
        return self.runtime_registry.get_global_mode()

    def _manifest_context(self, manifest: RunManifest) -> dict[str, Any]:
        return {
            "run_id": manifest.run_id,
            "strategy_name": manifest.strategy_name,
            "strategy": manifest.strategy_name,
            "mode": manifest.mode.value,
            "time_window": _time_window_label(manifest),
            "start_time": manifest.start_time,
            "end_time": manifest.end_time,
        }

    def _latest_market_state(self) -> list[dict[str, Any]]:
        if self.market_data_store is None:
            return []
        return self.market_data_store.fetch_latest_state(limit=200)

    def _pnl_row(self, manifest: RunManifest) -> dict[str, Any]:
        metrics = manifest.metrics_summary
        return {
            **self._manifest_context(manifest),
            "realized_pnl": _as_decimal(metrics.get("realized_pnl")),
            "unrealized_pnl": _as_decimal(metrics.get("unrealized_pnl")),
            "turnover": _as_decimal(metrics.get("turnover")),
            "max_drawdown": _as_decimal(metrics.get("max_drawdown")),
            "exposure_peak": _as_decimal(metrics.get("exposure_peak")),
            "win_rate": Decimal("1")
            if _as_decimal(metrics.get("realized_pnl"))
            + _as_decimal(metrics.get("unrealized_pnl"))
            > 0
            else Decimal("0"),
        }


def _matches_manifest_filters(
    context: dict[str, Any],
    manifest: RunManifest,
    filters: OperatorFilters,
) -> bool:
    if filters.strategy and context["strategy_name"] != filters.strategy:
        return False
    if filters.mode and context["mode"] != filters.mode:
        return False
    run_start = manifest.universe_snapshot.window_start or manifest.start_time
    run_end = manifest.universe_snapshot.window_end or manifest.end_time or manifest.start_time
    if filters.window_start and run_end < filters.window_start:
        return False
    if filters.window_end and run_start > filters.window_end:
        return False
    if not any([filters.market, filters.event, filters.token]):
        return True
    for mapping in manifest.universe_snapshot.token_mappings or [{}]:
        token = (
            mapping.get("token_id")
            or mapping.get("yes_token_id")
            or mapping.get("no_token_id")
        )
        market = mapping.get("market_id") or mapping.get("market")
        event = mapping.get("event_id") or mapping.get("condition_id") or mapping.get("question")
        if filters.market and market != filters.market:
            continue
        if filters.event and event != filters.event:
            continue
        if filters.token and token != filters.token:
            continue
        return True
    return False


def _matches_filters(context: dict[str, Any], filters: OperatorFilters) -> bool:
    if filters.strategy and context["strategy"] != filters.strategy:
        return False
    if filters.market and context["market"] != filters.market:
        return False
    if filters.event and context["event"] != filters.event:
        return False
    if filters.token and context["token"] != filters.token:
        return False
    if filters.mode and context["mode"] != filters.mode:
        return False
    if filters.status and context["state"] != filters.status:
        return False
    return True


def _matches_token(row: dict[str, Any], token: str | None) -> bool:
    return token is None or str(row.get("token_id")) == token


def _time_window_label(manifest: RunManifest) -> str:
    start = manifest.universe_snapshot.window_start or manifest.start_time
    end = manifest.universe_snapshot.window_end or manifest.end_time or manifest.start_time
    return f"{start.isoformat()} -> {end.isoformat()}"


def _as_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value))


def _average_decimal(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    return sum(values) / Decimal(len(values))


def _worst_block_state(states: list[NewOrderBlockState]) -> NewOrderBlockState:
    if not states:
        return NewOrderBlockState.ALLOWED
    if NewOrderBlockState.FULLY_BLOCKED in states:
        return NewOrderBlockState.FULLY_BLOCKED
    if NewOrderBlockState.PARTIALLY_BLOCKED in states:
        return NewOrderBlockState.PARTIALLY_BLOCKED
    return NewOrderBlockState.ALLOWED


def _aggregate_state(states: list[StrategyRuntimeState]) -> StrategyRuntimeState:
    if not states:
        return StrategyRuntimeState.FINISHED
    for candidate in (
        StrategyRuntimeState.ERROR,
        StrategyRuntimeState.BLOCKED,
        StrategyRuntimeState.RUNNING,
        StrategyRuntimeState.STARTING,
        StrategyRuntimeState.PAUSED,
        StrategyRuntimeState.FINISHED,
    ):
        if candidate in states:
            return candidate
    return StrategyRuntimeState.FINISHED


def _strategy_state_summary(snapshots: list[RuntimeStatusSnapshot]) -> dict[str, int]:
    summary = {state.value: 0 for state in StrategyRuntimeState}
    for snapshot in snapshots:
        summary[snapshot.state.value] += 1
    return summary


def _strategy_state_summary_from_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary = {state.value: 0 for state in StrategyRuntimeState}
    seen_run_ids: set[str] = set()
    for row in rows:
        run_id = str(row.get("run_id"))
        if run_id in seen_run_ids:
            continue
        seen_run_ids.add(run_id)
        state = str(row.get("state", StrategyRuntimeState.FINISHED.value))
        if state in summary:
            summary[state] += 1
    return summary


def _severity_for_snapshot(snapshot: RuntimeStatusSnapshot) -> str:
    if snapshot.state == StrategyRuntimeState.ERROR:
        return "Critical"
    if snapshot.state == StrategyRuntimeState.BLOCKED:
        return "Warning"
    if snapshot.alert_summary.Critical > 0:
        return "Critical"
    if snapshot.alert_summary.Warning > 0:
        return "Warning"
    return "Info"


def _severity_for_risk_decision(decision: dict[str, Any]) -> str:
    value = str(decision.get("decision"))
    if value == "REJECT":
        return "Critical"
    if value == "WARN":
        return "Warning"
    return "Info"


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None
