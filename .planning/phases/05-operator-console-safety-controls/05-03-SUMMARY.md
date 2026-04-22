---
phase: 05-operator-console-safety-controls
plan: 03
subsystem: operator-query-layer
tags: [queries, read-model, artifacts, metrics, streamlit]
requires:
  - phase: 05-operator-console-safety-controls
    provides: [operator runtime registry, safety controls]
  - phase: 04-strategy-research-workbench
    provides: [run manifests, artifact bundles, metrics summaries]
provides:
  - Operator query service
  - Shared filter vocabulary across homepage and secondary surfaces
  - Grouped analytics by strategy, market, event, and time window
affects: [operator-console, status-band, runs-artifacts]
tech-stack:
  added: []
  patterns: [artifact-backed-read-model, shared-filter-queries]
key-files:
  created:
    - src/polymarket_quant/services/operator_queries.py
    - tests/unit/test_operator_queries.py
  modified: []
key-decisions:
  - "The console reads through one query layer instead of embedding joins inside Streamlit components."
  - "Grouping by strategy remains the default, but market, event, and time_window aggregations are first-class."
  - "Runs/artifacts, positions/orders, pnl/exposure, and alerts timeline share one filter model."
patterns-established:
  - "Runtime snapshots and manifest bundles are joined into one operator context row per run/token mapping."
  - "Artifact parquet files are loaded lazily and cached per run and artifact type."
requirements-completed: [OPS-01, RISK-03]
duration: 0 min
completed: 2026-04-22
---

# Phase 5 Plan 03: Operator Queries Summary

**Unified operator read model for grouped overview, detail panes, timeline, and run artifact browsing**

## Performance

- **Duration:** 0 min
- **Started:** 2026-04-22T07:09:22Z
- **Completed:** 2026-04-22T07:09:22Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `OperatorQueryService` to merge runtime registry snapshots, run manifests, artifact bundles, and optional market-data/store inputs.
- Added grouped overview queries for `strategy`, `market`, `event`, and `time_window`, including `win_rate`, `turnover`, `drawdown`, and `exposure_peak`.
- Added shared-filter-aware reads for `Positions / Orders`, `PnL / Exposure`, `alerts_timeline`, `runs_artifacts`, and the top status band.
- Added tests covering grouping, filter propagation, overview/runtime joins, and manifest/artifact discovery.

## Task Commits

1. **Tasks 1-2: Operator read model + detail/timeline queries** - pending phase commit

## Files Created/Modified

- `src/polymarket_quant/services/operator_queries.py` - Query layer for overview, details, timeline, runs, and status band.
- `tests/unit/test_operator_queries.py` - Grouping and artifact-backed query coverage.

## Decisions Made

- Grouped `win_rate` is derived from positive-vs-nonpositive run outcomes until a more granular trade-outcome surface exists.
- Artifact bundles are the primary read source; optional store readers are treated as supplemental fallbacks.
- Timeline entries include both runtime heartbeat/state events and risk-decision artifacts so operators can see both status and causality.

## Deviations from Plan

- None.

## Issues Encountered

- None.

## User Setup Required

None.

## Next Phase Readiness

Phase 05-04 can render the operator homepage directly from the query service without embedding aggregation logic into the UI layer.

## Self-Check: PASSED

- `pytest tests/unit/test_operator_queries.py -q` -> 3 passed.
- `pytest -q` -> 144 passed.
- Required `rg` checks for grouped analytics, `last_heartbeat`, `alerts_timeline`, and `runs_artifacts` passed.

---
*Phase: 05-operator-console-safety-controls*
*Completed: 2026-04-22*
