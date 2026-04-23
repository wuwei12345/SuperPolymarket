---
phase: 06-automation-scheduled-reports
status: complete
researched_at: 2026-04-22
sources_checked: local_codebase, planning_artifacts
---

# Phase 6 Research: Automation + Scheduled Reports

## Research Goal

Answer what the planner needs to know to build Phase 6 well: a cron-friendly automation layer that reuses existing Polymarket simulator services, runs a conservative daily workflow, and emits human-readable reports plus structured run evidence without adding live trading or a daemon scheduler.

## Source-Backed Facts

### Existing execution and artifact surface

- `StrategyCliService` already resolves YAML/JSON config, runs strategies in `replay`, `research`, or `realtime_paper` mode, and writes `manifest.json` plus parquet and log artifacts.
- `RunArtifactBundleWriter` already persists run directories in a stable shape that reports can reference instead of scraping console output.
- `OperatorQueryService` already aggregates manifests, metrics, positions, orders, alerts, and artifacts for operator-facing views.

### Existing task entrypoints that automation should reuse

- `market_sync.py` already exposes a structured sync workflow and event/timeline model.
- `realtime_collector.py` already owns realtime ingestion, reconnect, and gap-fill behavior for market data.
- Phase 5 introduced operator runtime state, alert semantics, and mode/preflight boundaries that automation should summarize, not duplicate.

### Current gap that Phase 6 must close

- There is no single automation run model that captures which tasks were attempted, which succeeded, which were skipped, and where the resulting report was written.
- There is no standard CLI that chains market sync, health checks, strategy batch runs, and report generation into one repeatable job.
- There is no report builder that translates existing artifacts and operator summaries into a daily operator-friendly Markdown/HTML report.

### Constraints that must remain intact

- v1 remains simulation-first and Polymarket-only.
- `live-disabled` remains a protective boundary; Phase 6 must not imply live trading is available.
- `backfill` is intentionally excluded from the default scheduled chain and must stay sidecar/manual in this phase.
- Scheduling responsibility stays with cron or another host scheduler; Phase 6 should not grow a heavy internal daemon.

## Implementation Guidance

### Automation model

Introduce explicit automation-domain models for:

- automation run identity and timestamps
- resolved automation config
- per-task result/status
- skipped vs failed distinction
- report output references

These objects should be serializable so each automation run has its own factual record.

### Task orchestration

Build a lightweight runner that orchestrates existing services in order:

1. market sync
2. realtime health check
3. strategy batch run
4. report generation

Failure semantics must be graded:

- sync/health failures mark the run unhealthy but do not automatically stop reporting
- missing prerequisites can skip strategy execution
- report generation must still be attempted

### Report generation

The report builder should read from structured sources first:

- automation task results
- operator query summaries
- run manifests and metrics summaries
- alert and block state summaries

Markdown should be the canonical first output. HTML should be derived from the same structured report context rather than from a second independent data path.

### Configuration and invocation

Use one YAML config as the operator-facing contract for scheduled automation. It should declare:

- enabled tasks
- strategy list
- mode
- artifact/report roots
- daily window policy
- report output options

The CLI should be the same one-shot entrypoint used both manually and from cron.

### Storage and traceability

Phase 6 should write an automation-run directory or equivalent structured artifact set containing:

- resolved automation config
- task result summary
- paths to strategy run artifacts produced during the automation
- report file paths
- framework log

This keeps reports explainable and gives later audits a stable source of truth.

## Validation Architecture

Recommended automated checks:

- `pytest tests/unit/test_automation_models.py -q`
- `pytest tests/unit/test_automation_runner.py -q`
- `pytest tests/unit/test_report_builder.py -q`
- `pytest tests/unit/test_report_index.py -q`
- `pytest tests/unit/test_automation_cli.py -q`
- `pytest -q`

Recommended grep checks:

- `rg "AutomationRun|AutomationTaskResult|resolved_config" src/polymarket_quant/domain src/polymarket_quant/services`
- `rg "skip|failed|report generation|realtime_paper" src/polymarket_quant/services/automation_runner.py`
- `rg "Yesterday|Critical|Warning|Artifacts|PnL|drawdown" src/polymarket_quant/services/report_builder.py README.md`
- `rg "cron|automation" README.md src/polymarket_quant/services/automation_cli.py`

Manual smoke checks should focus on:

- one-shot CLI execution shape
- report readability
- cron example correctness

## Planning Implications

- Define automation-domain models and resolved config shape first; every later plan depends on a factual automation run record.
- Build graded task orchestration before report formatting, so reports can explain failures and skips honestly.
- Build the Markdown report path before HTML export, because Markdown is the canonical first artifact.
- Finish with CLI and README so the phase ships as an operator workflow rather than a set of disconnected services.

## External Sources

No external research was required. Phase 6 planning is constrained by the local codebase, the Phase 4 artifact contract, and the Phase 5 operator query and safety surfaces.

## RESEARCH COMPLETE
