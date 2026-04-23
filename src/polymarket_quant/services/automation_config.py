from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from polymarket_quant.domain.automation import (
    AutomationResolvedConfig,
    AutomationStrategyDefinition,
    AutomationTaskName,
    ReportFormat,
)
from polymarket_quant.domain.strategy import RunMode


DEFAULT_ENABLED_TASKS = [
    AutomationTaskName.MARKET_SYNC,
    AutomationTaskName.REALTIME_HEALTH_CHECK,
    AutomationTaskName.STRATEGY_BATCH,
    AutomationTaskName.REPORT_GENERATION,
]

DEFAULT_REPORT_FORMATS = [ReportFormat.MARKDOWN, ReportFormat.HTML]


def load_automation_config(path: str | Path) -> AutomationResolvedConfig:
    config_path = Path(path)
    text = config_path.read_text()
    if config_path.suffix.lower() in {".yaml", ".yml"}:
        loaded = yaml.safe_load(text) or {}
    elif config_path.suffix.lower() == ".json":
        loaded = json.loads(text)
    else:
        raise ValueError("automation config path must be YAML or JSON")
    if not isinstance(loaded, dict):
        raise ValueError("automation config must deserialize into an object")
    return resolve_automation_config(
        loaded,
        config_base_dir=config_path.parent,
        workspace_root=Path.cwd(),
        raw_config_path=config_path,
    )


def resolve_automation_config(
    raw_config: dict[str, Any],
    *,
    config_base_dir: str | Path = ".",
    workspace_root: str | Path = ".",
    raw_config_path: str | Path | None = None,
) -> AutomationResolvedConfig:
    config_base_path = Path(config_base_dir)
    workspace_root_path = Path(workspace_root)
    enabled_tasks = _parse_enabled_tasks(raw_config.get("enabled_tasks"))
    report_formats = _parse_report_formats(raw_config.get("report_formats"))
    strategies = _parse_strategies(
        raw_config.get("strategies"),
        config_base_path=config_base_path,
    )
    return AutomationResolvedConfig(
        environment=str(raw_config.get("environment", "local")),
        mode=RunMode(raw_config.get("mode", RunMode.REALTIME_PAPER)),
        enabled_tasks=enabled_tasks,
        strategies=strategies,
        artifact_root=str(
            _resolve_path(workspace_root_path, raw_config.get("artifact_root", "data/runs"))
        ),
        automation_root=str(
            _resolve_path(
                workspace_root_path,
                raw_config.get("automation_root", "data/automation"),
            )
        ),
        report_output_dir=str(
            _resolve_path(
                workspace_root_path,
                raw_config.get("report_output_dir", "data/reports/daily"),
            )
        ),
        market_store_path=str(
            _resolve_path(
                workspace_root_path,
                raw_config.get("market_store_path", "data/markets.sqlite3"),
            )
        ),
        report_formats=report_formats,
        window_policy=str(raw_config.get("window_policy", "calendar_yesterday")),
        timezone=str(raw_config.get("timezone", "UTC")),
        raw_config_path=None if raw_config_path is None else str(Path(raw_config_path).resolve()),
        metadata={k: v for k, v in raw_config.items() if k not in _KNOWN_CONFIG_KEYS},
    )


_KNOWN_CONFIG_KEYS = {
    "environment",
    "mode",
    "enabled_tasks",
    "strategies",
    "artifact_root",
    "automation_root",
    "report_output_dir",
    "market_store_path",
    "report_formats",
    "window_policy",
    "timezone",
}


def _parse_enabled_tasks(raw_tasks: Any) -> list[AutomationTaskName]:
    values = raw_tasks or [task.value for task in DEFAULT_ENABLED_TASKS]
    if not isinstance(values, list):
        raise ValueError("enabled_tasks must be a list")
    parsed: list[AutomationTaskName] = []
    for value in values:
        parsed.append(AutomationTaskName(str(value)))
    return parsed


def _parse_report_formats(raw_formats: Any) -> list[ReportFormat]:
    values = raw_formats or [report_format.value for report_format in DEFAULT_REPORT_FORMATS]
    if not isinstance(values, list):
        raise ValueError("report_formats must be a list")
    parsed = [ReportFormat(str(value)) for value in values]
    if not parsed:
        raise ValueError("report_formats cannot be empty")
    return parsed


def _parse_strategies(
    raw_strategies: Any,
    *,
    config_base_path: Path,
) -> list[AutomationStrategyDefinition]:
    if raw_strategies is None:
        return []
    if not isinstance(raw_strategies, list):
        raise ValueError("strategies must be a list")
    strategies: list[AutomationStrategyDefinition] = []
    for raw_strategy in raw_strategies:
        if not isinstance(raw_strategy, dict):
            raise ValueError("each strategy entry must be an object")
        strategies.append(
            AutomationStrategyDefinition(
                name=str(raw_strategy.get("name", "strategy")),
                strategy_class=str(raw_strategy.get("strategy_class", "")),
                config_path=str(
                    _resolve_path(config_base_path, raw_strategy.get("config_path", ""))
                ),
                enabled=bool(raw_strategy.get("enabled", True)),
            )
        )
    return strategies


def _resolve_path(base_path: Path, raw_path: Any) -> Path:
    path = Path(str(raw_path))
    if path.is_absolute():
        return path
    return (base_path / path).resolve()
