---
phase: 04-strategy-research-workbench
plan: 01
subsystem: strategy-contract
tags: [strategy, signal, manifest, base-class]
requires:
  - phase: 03-05
    provides: [PaperExchangeService]
provides:
  - Typed Phase 4 strategy and run domain models
  - Shared `BaseStrategy` lifecycle contract
  - Unit tests for strategy contract and manifest/config schemas
affects: [replay-runtime, realtime-paper-runner, cli]
tech-stack:
  added: []
  patterns: [pydantic-domain-models, explicit lifecycle contract]
key-files:
  created:
    - src/polymarket_quant/domain/strategy.py
    - src/polymarket_quant/strategy/__init__.py
    - src/polymarket_quant/strategy/base.py
    - tests/unit/test_strategy_models.py
  modified: []
key-decisions:
  - "Target-based signals are first-class and separate from `OrderIntent`."
  - "Replay and realtime paper share one strategy lifecycle contract."
patterns-established:
  - "Phase 4 strategy/runtime types live outside `domain/simulation.py`."
requirements-completed: []
duration: 0 min
completed: 2026-04-21
---

# Phase 4 Plan 01: Strategy Contract Summary

**Typed strategy lifecycle, signal schema, resolved config, and run manifest foundation**

## Performance

- **Duration:** 0 min
- **Started:** 2026-04-21T00:00:00Z
- **Completed:** 2026-04-21T00:00:00Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Added `RunMode`, `StrategyEventType`, `StrategySignal`, `StrategyEvent`, `UniverseSnapshot`, `ResolvedRunConfig`, `StrategyContextSnapshot`, and `RunManifest`.
- Added `BaseStrategy` with `on_init`, `on_event`, `on_clock`, and `on_finish`.
- Added tests for signal validation, resolved config structure, manifest metadata, and base strategy lifecycle.

## Task Commits

1. **Tasks 1-3: Strategy contract foundation** - pending phase commit

## Files Created/Modified

- `src/polymarket_quant/domain/strategy.py` - Phase 4 strategy and run models.
- `src/polymarket_quant/strategy/base.py` - Shared strategy lifecycle contract.
- `src/polymarket_quant/strategy/__init__.py` - Strategy exports.
- `tests/unit/test_strategy_models.py` - Strategy contract tests.

## Decisions Made

- `target_exposure` is the primary Phase 4 signal semantic.
- Base strategy methods return lists of `StrategySignal` by default.
- Run manifest and resolved config are explicit typed objects from the start.

## Deviations from Plan

None.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

Plan 04-02 can now write typed manifests/artifact bundles, and Plans 04-03/04-04 can build runtimes against the shared strategy contract.

## Self-Check: PASSED

- `pytest tests/unit/test_strategy_models.py -q` -> 7 passed.
- `pytest -q` -> 118 passed.
- Required `rg` checks for strategy models and lifecycle methods passed.

---
*Phase: 04-strategy-research-workbench*
*Completed: 2026-04-21*
