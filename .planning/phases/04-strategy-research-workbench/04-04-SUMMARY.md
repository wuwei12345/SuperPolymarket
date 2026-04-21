---
phase: 04-strategy-research-workbench
plan: 04
subsystem: realtime-paper-runner
tags: [signals, sizing, execution, realtime]
requires:
  - phase: 04-01
    provides: [StrategySignal, StrategyContextSnapshot, BaseStrategy]
  - phase: 04-03
    provides: [StrategyRuntime]
  - phase: 03-simulation-exchange-portfolio-ledger
    provides: [PaperExchangeService]
provides:
  - Target-based signal translation service
  - Realtime paper strategy runner
  - Execution and risk feedback loop into shared runtime context
affects: [cli, experiment-tracking]
tech-stack:
  added: []
  patterns: [signal-to-intent-adapter, shared-realtime-feedback]
key-files:
  created:
    - src/polymarket_quant/services/signal_execution.py
    - src/polymarket_quant/services/realtime_strategy_runner.py
    - tests/unit/test_signal_execution.py
  modified: []
key-decisions:
  - "Strategies continue to emit target-based signals; sizing and execution stay outside strategy code."
  - "Realtime paper mode reuses `StrategyRuntime` and routes all intents through `PaperExchangeService`."
patterns-established:
  - "Execution feedback is written back as `StrategyEvent` records rather than mutating strategy state directly."
requirements-completed: []
duration: 0 min
completed: 2026-04-21
---

# Phase 4 Plan 04: Realtime Paper Runner Summary

**Target-based signal translation plus realtime routing through the Phase 3 paper exchange**

## Performance

- **Duration:** 0 min
- **Started:** 2026-04-21T00:00:00Z
- **Completed:** 2026-04-21T00:00:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Added `SignalExecutionService` to translate `target_exposure` or `target_position` signals into `OrderIntent` deltas.
- Added `RealtimeStrategyRunner` to reuse the shared runtime lifecycle while routing execution through `PaperExchangeService`.
- Fed risk decisions, fills, positions, cash, and open-order state back into runtime context as strategy events.
- Added tests for target-exposure sizing, target-position fallback, realtime paper routing, and execution feedback propagation.

## Task Commits

1. **Tasks 1-2: Signal execution + realtime runner** - pending phase commit

## Files Created/Modified

- `src/polymarket_quant/services/signal_execution.py` - Target-based signal translation into `OrderIntent`.
- `src/polymarket_quant/services/realtime_strategy_runner.py` - Realtime paper orchestration on top of `StrategyRuntime`.
- `tests/unit/test_signal_execution.py` - Translation and realtime feedback tests.

## Decisions Made

- `target_exposure` defaults to `fraction_of_equity` sizing and can be switched to `notional` through resolved config.
- Execution pricing uses aggressive side-aware quotes first, then midpoint/last-trade fallbacks.
- Runtime feedback uses `StrategyEventType.RISK` and `StrategyEventType.EXECUTION` so replay and realtime stay on one contract.

## Deviations from Plan

- None.

## Issues Encountered

- Realtime fill assertions required zero submit latency in unit tests; this was handled by injecting a `FillEngineConfig` into the test exchange instead of weakening the production default.

## User Setup Required

None.

## Next Phase Readiness

Plan 04-05 can now wire CLI entrypoints, metrics, and run-bundle persistence on top of replay and realtime execution modes.

## Self-Check: PASSED

- `pytest tests/unit/test_signal_execution.py -q` -> 4 passed.
- `pytest -q` -> 128 passed.
- Required `rg` checks for target translation and realtime routing passed.

---
*Phase: 04-strategy-research-workbench*
*Completed: 2026-04-21*
