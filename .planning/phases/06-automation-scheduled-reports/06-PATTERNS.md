---
phase: 06-automation-scheduled-reports
status: complete
created: 2026-04-22
---

# Phase 6 Pattern Map

## Existing Patterns To Reuse

### CLI and resolved-config execution

Closest analog:

- `src/polymarket_quant/services/strategy_cli.py`

Pattern:

- CLI/service layer resolves config before execution.
- Effective config is persisted, not just the input path.
- Orchestration returns structured results rather than loose print output.

Apply to:

- `src/polymarket_quant/services/automation_cli.py`
- `src/polymarket_quant/services/automation_runner.py`
- automation manifest/result writing

### Structured artifact bundle writing

Closest analog:

- `src/polymarket_quant/services/run_artifacts.py`

Pattern:

- One run directory per execution
- canonical `manifest.json`
- stable artifact filenames
- logs written alongside structured data

Apply to:

- automation run bundle layout
- report output directory conventions
- report index records

### Timeline/task-event style

Closest analogs:

- `src/polymarket_quant/services/market_sync.py`
- `src/polymarket_quant/services/backfill.py`
- `src/polymarket_quant/services/realtime_collector.py`

Pattern:

- explicit started / retry / failed / completed states
- concise factual event rows
- source-aware status reporting

Apply to:

- automation task status model
- framework log rows
- health-check reporting

### Query/read-model reuse

Closest analog:

- `src/polymarket_quant/services/operator_queries.py`

Pattern:

- report/query layer reads structured storage and returns presentation-ready rows
- keep joins and derived metrics out of UI or CLI wrappers
- favor deterministic, testable read-side helpers

Apply to:

- report context assembly
- runs/artifacts report section
- daily strategy summary aggregation

### Documentation and operator workflow

Closest analogs:

- `README.md`
- existing service `main()` entrypoints

Pattern:

- README gives direct commands with minimal ceremony
- examples map cleanly to concrete module entrypoints
- operational docs stay aligned with actual code paths

Apply to:

- automation CLI usage
- cron examples
- report output path documentation

## Suggested File Ownership By Plan

| Plan | Primary Files | Closest Analog |
|------|---------------|----------------|
| 06-01 | `domain/automation.py`, `services/automation_config.py`, tests | `domain/operator.py`, `strategy_cli.py` |
| 06-02 | `services/automation_runner.py`, `services/automation_tasks.py`, tests | `market_sync.py`, `strategy_cli.py` |
| 06-03 | `services/report_builder.py`, `services/report_templates.py`, tests | `operator_queries.py`, `run_artifacts.py` |
| 06-04 | `services/report_outputs.py` or report-index helpers, tests | `run_artifacts.py`, `operator_queries.py` |
| 06-05 | `services/automation_cli.py`, sample config, README, tests | `strategy_cli.py`, existing `main()` services |

## Landmines

- Do not build a daemon scheduler or background worker system in this phase.
- Do not silently run `backfill` as part of the default automation chain.
- Do not make report generation depend on every upstream task succeeding.
- Do not scrape raw logs when manifests, parquet artifacts, and operator queries already provide structured facts.
- Do not weaken the `live-disabled` boundary or imply unattended live trading exists.
- Do not hide skipped strategy runs; skipped due to failed prerequisites must be explicit in the automation result.
- Do not let cron-specific behavior diverge from the normal CLI one-shot path.

## PATTERN MAPPING COMPLETE
