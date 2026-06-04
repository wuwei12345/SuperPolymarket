from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel

from polymarket_quant.domain.strategy import RunManifest


ARTIFACT_FILE_NAMES = {
    "signals": "signals.parquet",
    "order_intents": "order_intents.parquet",
    "orders": "orders.parquet",
    "fills": "fills.parquet",
    "positions": "positions.parquet",
    "cash_ledger": "cash_ledger.parquet",
    "pnl_timeline": "pnl_timeline.parquet",
    "risk_decisions": "risk_decisions.parquet",
}


class RunArtifactBundleWriter:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)

    def write_bundle(
        self,
        manifest: RunManifest,
        signals: Sequence[Mapping[str, Any] | BaseModel] = (),
        order_intents: Sequence[Mapping[str, Any] | BaseModel] = (),
        orders: Sequence[Mapping[str, Any] | BaseModel] = (),
        fills: Sequence[Mapping[str, Any] | BaseModel] = (),
        positions: Sequence[Mapping[str, Any] | BaseModel] = (),
        cash_ledger: Sequence[Mapping[str, Any] | BaseModel] = (),
        pnl_timeline: Sequence[Mapping[str, Any] | BaseModel] = (),
        risk_decisions: Sequence[Mapping[str, Any] | BaseModel] = (),
        strategy_log: str = "",
        framework_log: str = "",
    ) -> RunManifest:
        run_dir = self.base_dir / manifest.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self._clear_stale_artifacts(run_dir)

        artifact_files = dict(manifest.artifact_files)
        for artifact_name, rows in {
            "signals": signals,
            "order_intents": order_intents,
            "orders": orders,
            "fills": fills,
            "positions": positions,
            "cash_ledger": cash_ledger,
            "pnl_timeline": pnl_timeline,
            "risk_decisions": risk_decisions,
        }.items():
            if not rows:
                continue
            file_name = ARTIFACT_FILE_NAMES[artifact_name]
            self._write_parquet(run_dir / file_name, rows)
            artifact_files[artifact_name] = file_name

        strategy_log_name = "strategy.log"
        framework_log_name = "framework.log"
        (run_dir / strategy_log_name).write_text(strategy_log)
        (run_dir / framework_log_name).write_text(framework_log)
        artifact_files["strategy_log"] = strategy_log_name
        artifact_files["framework_log"] = framework_log_name

        updated_manifest = manifest.model_copy(update={"artifact_files": artifact_files})
        manifest_path = run_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(updated_manifest.model_dump(mode="json"), indent=2, sort_keys=True)
        )
        return updated_manifest

    @staticmethod
    def _clear_stale_artifacts(run_dir: Path) -> None:
        stale_names = {
            "manifest.json",
            "strategy.log",
            "framework.log",
            *ARTIFACT_FILE_NAMES.values(),
        }
        for file_name in stale_names:
            path = run_dir / file_name
            if path.exists() and path.is_file():
                path.unlink()

    @staticmethod
    def _write_parquet(
        path: Path, rows: Sequence[Mapping[str, Any] | BaseModel]
    ) -> None:
        pd.DataFrame([_row_to_dict(row) for row in rows]).to_parquet(path, index=False)


def _row_to_dict(row: Mapping[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(row, BaseModel):
        return _sanitize_nested(row.model_dump(mode="json"))
    return _sanitize_nested(dict(row))


def _sanitize_nested(value: Any) -> Any:
    if isinstance(value, dict):
        if not value:
            return None
        return {key: _sanitize_nested(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_sanitize_nested(child) for child in value]
    return value
