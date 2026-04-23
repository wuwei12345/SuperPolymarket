from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any


RUN_OVERVIEW_TITLE = "Run Overview"
MARKET_SYNC_TITLE = "Market Sync Summary"
REALTIME_HEALTH_TITLE = "Realtime Health Summary"
STRATEGY_SUMMARY_TITLE = "Strategy Run Summary"
PNL_EXPOSURE_TITLE = "PnL / Drawdown / Exposure"
ALERTS_TITLE = "Alerts Summary"
RUNS_ARTIFACTS_TITLE = "Runs / Artifacts"


def render_key_values(values: Sequence[tuple[str, Any]]) -> str:
    return "\n".join(f"- {label}: {value}" for label, value in values)


def render_task_status_lines(task_results: Iterable[dict[str, Any]]) -> str:
    lines = []
    for task_result in task_results:
        lines.append(
            f"- {task_result['task_name']}: {task_result['status']} ({task_result['message']})"
        )
    return "\n".join(lines) or "- none"


def render_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    empty_message: str = "_No data._",
) -> str:
    if not rows:
        return empty_message
    header_line = "| " + " | ".join(headers) + " |"
    divider_line = "| " + " | ".join("---" for _ in headers) + " |"
    body_lines = ["| " + " | ".join(_stringify(cell) for cell in row) + " |" for row in rows]
    return "\n".join([header_line, divider_line, *body_lines])


def isoformat(value: datetime | None) -> str:
    if value is None:
        return "n/a"
    return value.isoformat()


def _stringify(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
