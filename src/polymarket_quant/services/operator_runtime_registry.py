from __future__ import annotations

from datetime import datetime

from polymarket_quant.domain.operator import (
    GlobalMode,
    LocalRunMode,
    NewOrderBlockState,
    RuntimeStatusSnapshot,
    StrategyRuntimeState,
)
from polymarket_quant.domain.market_data import utc_now


class OperatorRuntimeRegistry:
    def __init__(self, global_mode: GlobalMode = GlobalMode.LIVE_DISABLED) -> None:
        self._global_mode = global_mode
        self._runs: dict[str, RuntimeStatusSnapshot] = {}

    def set_global_mode(self, mode: GlobalMode) -> GlobalMode:
        self._global_mode = mode
        now = utc_now()
        for run_id, snapshot in self._runs.items():
            self._runs[run_id] = snapshot.model_copy(
                update={"global_mode": mode, "updated_at": now}
            )
        return self._global_mode

    def get_global_mode(self) -> GlobalMode:
        return self._global_mode

    def start_run(
        self,
        *,
        run_id: str,
        strategy_name: str,
        strategy_version: str = "dev",
        local_mode: LocalRunMode,
        state: StrategyRuntimeState = StrategyRuntimeState.STARTING,
        new_order_status: NewOrderBlockState = NewOrderBlockState.ALLOWED,
        heartbeat_at: datetime | None = None,
    ) -> RuntimeStatusSnapshot:
        heartbeat = heartbeat_at or utc_now()
        snapshot = RuntimeStatusSnapshot(
            run_id=run_id,
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            global_mode=self._global_mode,
            local_mode=local_mode,
            state=state,
            new_order_status=new_order_status,
            last_heartbeat=heartbeat,
            updated_at=heartbeat,
        )
        self._runs[run_id] = snapshot
        return snapshot

    def heartbeat(
        self,
        run_id: str,
        *,
        at: datetime | None = None,
        state: StrategyRuntimeState | None = None,
        new_order_status: NewOrderBlockState | None = None,
        active_positions: int | None = None,
        open_orders: int | None = None,
        latest_pnl: float | None = None,
        latest_drawdown: float | None = None,
    ) -> RuntimeStatusSnapshot:
        snapshot = self._require_run(run_id)
        heartbeat_at = at or utc_now()
        update: dict[str, object] = {
            "last_heartbeat": heartbeat_at,
            "updated_at": heartbeat_at,
        }
        if state is not None:
            update["state"] = state
        if new_order_status is not None:
            update["new_order_status"] = new_order_status
        if active_positions is not None:
            update["active_positions"] = active_positions
        if open_orders is not None:
            update["open_orders"] = open_orders
        if latest_pnl is not None:
            update["latest_pnl"] = latest_pnl
        if latest_drawdown is not None:
            update["latest_drawdown"] = latest_drawdown
        updated = snapshot.model_copy(update=update)
        self._runs[run_id] = updated
        return updated

    def finish_run(
        self,
        run_id: str,
        *,
        at: datetime | None = None,
        latest_pnl: float | None = None,
        latest_drawdown: float | None = None,
    ) -> RuntimeStatusSnapshot:
        return self.heartbeat(
            run_id,
            at=at,
            state=StrategyRuntimeState.FINISHED,
            latest_pnl=latest_pnl,
            latest_drawdown=latest_drawdown,
        )

    def fail_run(
        self, run_id: str, message: str, *, at: datetime | None = None
    ) -> RuntimeStatusSnapshot:
        snapshot = self._require_run(run_id)
        failure_at = at or utc_now()
        updated = snapshot.model_copy(
            update={
                "state": StrategyRuntimeState.ERROR,
                "error_message": message,
                "last_heartbeat": failure_at,
                "updated_at": failure_at,
            }
        )
        self._runs[run_id] = updated
        return updated

    def get_run(self, run_id: str) -> RuntimeStatusSnapshot | None:
        return self._runs.get(run_id)

    def list_runs(self) -> list[RuntimeStatusSnapshot]:
        return sorted(
            self._runs.values(),
            key=lambda snapshot: snapshot.updated_at,
            reverse=True,
        )

    def _require_run(self, run_id: str) -> RuntimeStatusSnapshot:
        snapshot = self._runs.get(run_id)
        if snapshot is None:
            raise KeyError(f"unknown run: {run_id}")
        return snapshot
