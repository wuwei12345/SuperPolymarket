---
phase: 04-strategy-research-workbench
plan: 05
subsystem: cli-and-metrics
tags: [cli, metrics, yaml, reproducibility]
requires:
  - phase: 04-02
    provides: [RunArtifactBundleWriter]
  - phase: 04-03
    provides: [ReplayRuntime, StrategyRuntime]
  - phase: 04-04
    provides: [RealtimeStrategyRunner, SignalExecutionService]
provides:
  - Experiment metrics service
  - YAML/JSON strategy runtime CLI service
  - Phase 4 README and service exports
affects: [phase-5-ops, experiment-comparison]
tech-stack:
  added: [PyYAML]
  patterns: [resolved-config-manifest, factual-run-metrics]
key-files:
  created:
    - src/polymarket_quant/services/experiment_metrics.py
    - src/polymarket_quant/services/strategy_cli.py
    - tests/unit/test_strategy_cli.py
  modified:
    - README.md
    - pyproject.toml
    - src/polymarket_quant/services/__init__.py
    - src/polymarket_quant/services/realtime_strategy_runner.py
key-decisions:
  - "Resolved config is persisted from effective runtime values, not file paths or implicit defaults."
  - "Metrics are computed from factual artifacts such as intents, fills, positions, pnl rows, and risk decisions."
patterns-established:
  - "One CLI service dispatches replay, research, and realtime paper modes over the same strategy contract."
requirements-completed: []
duration: 0 min
completed: 2026-04-21
---

# Phase 4 Plan 05: CLI and Metrics Summary

**User-facing strategy runtime entry path with resolved config, artifact persistence, and factual run metrics**

## Performance

- **Duration:** 0 min
- **Started:** 2026-04-21T00:00:00Z
- **Completed:** 2026-04-21T00:00:00Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Added `ExperimentMetricsService` for total return, realized/unrealized PnL, turnover, fill rate, cancel rate, average holding time, max drawdown, exposure peak, reject count, and slippage metrics.
- Added `StrategyCliService` to load YAML/JSON config, resolve defaults into `ResolvedRunConfig`, dispatch replay/research/realtime paper modes, and persist `manifest.json` plus artifact bundles.
- Added public `on_init` support to `RealtimeStrategyRunner` so realtime paper uses the full strategy lifecycle.
- Updated README to document the Phase 4 runtime surface, strategy lifecycle, target-based signals, CLI-first workflow, and artifact directory layout.
- Added `PyYAML` to project dependencies and created CLI/metrics/doc tests.

## Task Commits

1. **Tasks 1-3: Metrics, CLI, docs** - pending phase commit

## Files Created/Modified

- `src/polymarket_quant/services/experiment_metrics.py` - Factual run-summary metrics.
- `src/polymarket_quant/services/strategy_cli.py` - YAML/JSON config entrypoint and mode dispatch.
- `tests/unit/test_strategy_cli.py` - Metrics, CLI, realtime-paper, and README coverage.
- `README.md` - Phase 4 runtime documentation.
- `pyproject.toml` - Added `PyYAML`.
- `src/polymarket_quant/services/__init__.py` - Exported Phase 4 public services.
- `src/polymarket_quant/services/realtime_strategy_runner.py` - Added public init dispatch.

## Decisions Made

- `research` mode reuses the replay runtime path while preserving a distinct manifest mode.
- Default realtime-paper constraints and snapshots can be derived from runtime market context when explicit providers are not injected.
- Manifest metrics remain JSON-serializable even when in-memory summaries use `Decimal`.

## Deviations from Plan

- None.

## Issues Encountered

- The local environment did not include a YAML parser, so `PyYAML` was added to dependencies and installed before verification.

## User Setup Required

- Run `pip install -e .` or otherwise install project dependencies before using YAML configs outside this session.

## Next Phase Readiness

Phase 4 now has a stable research entrypoint that can be consumed by later operator and experiment-comparison work.

## Self-Check: PASSED

- `pytest tests/unit/test_strategy_cli.py -q` -> 5 passed.
- `pytest -q` -> 133 passed.
- Required `rg` checks for CLI config support, metrics fields, and README scope passed.

---
*Phase: 04-strategy-research-workbench*
*Completed: 2026-04-21*
