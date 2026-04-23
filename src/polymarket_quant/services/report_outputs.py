from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path

from polymarket_quant.domain.automation import AutomationRun, ReportFormat, ReportReference


def write_report_outputs(
    report_output_dir: str | Path,
    automation_run: AutomationRun,
    markdown_report: str,
    *,
    report_formats: list[ReportFormat],
    window_start: datetime,
    window_end: datetime,
) -> ReportReference:
    base_dir = Path(report_output_dir)
    report_day_dir = base_dir / window_start.date().isoformat()
    report_day_dir.mkdir(parents=True, exist_ok=True)
    stem = automation_run.run_id
    markdown_path = report_day_dir / f"{stem}.md"
    markdown_path.write_text(markdown_report)

    html_path: Path | None = None
    if ReportFormat.HTML in report_formats:
        html_path = report_day_dir / f"{stem}.html"
        html_path.write_text(_markdown_to_html(markdown_report, title=automation_run.run_id))

    report_reference = ReportReference(
        window_start=window_start,
        window_end=window_end,
        markdown_path=str(markdown_path),
        html_path=None if html_path is None else str(html_path),
    )
    index_path = write_report_index(base_dir, automation_run, report_reference)
    return report_reference.model_copy(update={"index_path": str(index_path)})


def write_report_index(
    report_output_dir: str | Path,
    automation_run: AutomationRun,
    report_reference: ReportReference,
) -> Path:
    base_dir = Path(report_output_dir)
    base_dir.mkdir(parents=True, exist_ok=True)
    index_path = base_dir / "index.jsonl"
    entry = {
        "run_id": automation_run.run_id,
        "environment": automation_run.environment,
        "mode": automation_run.mode.value,
        "window_start": report_reference.window_start.isoformat(),
        "window_end": report_reference.window_end.isoformat(),
        "markdown_path": report_reference.markdown_path,
        "html_path": report_reference.html_path,
        "created_at": automation_run.created_at.isoformat(),
    }
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return index_path


def _markdown_to_html(markdown_report: str, *, title: str) -> str:
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        f"  <title>{escape(title)}</title>\n"
        "  <style>body{font-family:ui-monospace, SFMono-Regular, monospace;max-width:1000px;margin:32px auto;padding:0 16px;line-height:1.5;}pre{white-space:pre-wrap;}</style>\n"
        "</head>\n"
        "<body>\n"
        f"<pre>{escape(markdown_report)}</pre>\n"
        "</body>\n"
        "</html>\n"
    )
