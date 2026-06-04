from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from polymarket_quant.domain.automation import AutomationRun
from polymarket_quant.domain.market_data import utc_now
from polymarket_quant.services.market_display import MarketDisplayService
from polymarket_quant.services.operator_queries import OperatorFilters, OperatorQueryService


class DashboardSnapshotService:
    def __init__(
        self,
        query_service: OperatorQueryService,
        *,
        snapshot_path: str | Path = "data/runtime/latest_snapshot.json",
        market_display_service: MarketDisplayService | None = None,
    ) -> None:
        self.query_service = query_service
        self.snapshot_path = Path(snapshot_path)
        self.market_display_service = market_display_service

    def build_snapshot(
        self,
        *,
        filters: OperatorFilters | None = None,
        automation_run: AutomationRun | None = None,
        generated_at: datetime | None = None,
    ) -> dict[str, Any]:
        filters = filters or OperatorFilters()
        latest_strategy_run_id = _recent_strategy_run_id(
            automation_run
        ) or self.query_service.latest_strategy_run_id(filters)
        return {
            "schema_version": 1,
            "generated_at": generated_at or utc_now(),
            "automation_run_id": automation_run.run_id if automation_run is not None else None,
            "recent_run_id": latest_strategy_run_id,
            "latest_strategy_run_id": latest_strategy_run_id,
            "recent_report_path": _recent_report_path(automation_run),
            "summary_cards": self.query_service.simulation_summary(filters),
            "curves": self.query_service.simulation_curves(filters),
            "current_positions": self.query_service.simulation_positions(filters),
            "recent_simulated_trades": self.query_service.simulation_trades(filters),
            "market_cards": self.market_display_service.market_cards(filters)
            if self.market_display_service is not None
            else [],
            "recent_simulated_trades_display": self.market_display_service.recent_trades(filters)
            if self.market_display_service is not None
            else [],
            "alert_summary": self.query_service.risk_alert_summary(filters),
        }

    def write_latest(
        self,
        *,
        filters: OperatorFilters | None = None,
        automation_run: AutomationRun | None = None,
        generated_at: datetime | None = None,
    ) -> dict[str, Any]:
        snapshot = self.build_snapshot(
            filters=filters,
            automation_run=automation_run,
            generated_at=generated_at,
        )
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.snapshot_path.with_suffix(f"{self.snapshot_path.suffix}.tmp")
        temp_path.write_text(json.dumps(snapshot, default=_json_default, indent=2, sort_keys=True))
        temp_path.replace(self.snapshot_path)
        return snapshot

    def load_latest(self) -> dict[str, Any] | None:
        if not self.snapshot_path.exists():
            return None
        return json.loads(self.snapshot_path.read_text())


def _recent_strategy_run_id(automation_run: AutomationRun | None) -> str | None:
    if automation_run is None:
        return None
    for task_result in reversed(automation_run.task_results):
        if task_result.run_ids:
            return task_result.run_ids[-1]
    return None


def _recent_report_path(automation_run: AutomationRun | None) -> str | None:
    if automation_run is None or automation_run.report is None:
        return None
    return automation_run.report.html_path or automation_run.report.markdown_path


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
