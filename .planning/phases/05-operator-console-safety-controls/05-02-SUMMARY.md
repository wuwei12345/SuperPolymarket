---
phase: 05-operator-console-safety-controls
plan: 02
subsystem: safety-controls
tags: [risk, safety, preflight, liquidity, expiry]
requires:
  - phase: 05-operator-console-safety-controls
    provides: [operator runtime registry, global mode, local mode]
  - phase: 03-simulation-exchange-portfolio-ledger
    provides: [risk semantics, reject vs warn behavior]
provides:
  - Operator safety evaluation service
  - Action-aware order gate semantics
  - Global mode preflight checks
affects: [operator-console, mode-switching, runtime-guardrails]
tech-stack:
  added: []
  patterns: [typed-safety-evaluation, action-aware-blocking]
key-files:
  created:
    - src/polymarket_quant/services/operator_safety.py
    - tests/unit/test_operator_safety.py
  modified: []
key-decisions:
  - "Critical expiry and liquidity alerts block only increase_exposure actions while keeping reduce, close, and risk_release available."
  - "Connection gaps, market closure, and mode unavailability escalate to full new-order blocking."
  - "Mode preflight treats live-disabled as a protective boundary and blocks paper mode on missing or down critical connections."
patterns-established:
  - "Operator safety is expressed as typed alerts plus a derived new-order block state."
  - "Mode changes consume a preflight result instead of inventing UI-only rules."
requirements-completed: [RISK-02, OPS-03]
duration: 0 min
completed: 2026-04-22
---

# Phase 5 Plan 02: Safety Controls Summary

**Conservative safety evaluation for expiry, liquidity, connections, and mode switching with action-aware order gating**

## Performance

- **Duration:** 0 min
- **Started:** 2026-04-22T07:09:22Z
- **Completed:** 2026-04-22T07:09:22Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `OperatorSafetyService` to convert market/runtime facts into `Info / Warning / Critical` alerts and `allowed / partially blocked / fully blocked` new-order state.
- Encoded the locked thresholds for expiry, spread, top-of-book depth, recent trade activity, gap_fill instability, and book integrity.
- Added action-aware gating so critical expiry/liquidity states block only `increase_exposure`, while `reduce`, `close`, and `risk_release` remain allowed.
- Added typed mode `preflight` checks so the UI can show blockers and warnings before any global-mode confirmation.

## Task Commits

1. **Tasks 1-2: Safety evaluation + mode preflight** - pending phase commit

## Files Created/Modified

- `src/polymarket_quant/services/operator_safety.py` - Safety evaluation, action gate, and preflight service.
- `tests/unit/test_operator_safety.py` - Threshold, gate, and preflight coverage.

## Decisions Made

- Liquidity warnings and criticals are modeled as separate alert records instead of collapsing to a single score, so the console can explain why it blocked.
- Book completeness treats missing top-of-book depth on one side as a warning even when best bid/ask prices are present.
- Preflight allows switching into `live-disabled` with confirmation but never treats it as a live-trading path.

## Deviations from Plan

- None.

## Issues Encountered

- Initial book-integrity logic only warned when price sides were missing. It was tightened to also warn on missing top-of-book depth for one side so the liquidity contract matched the locked Phase 5 semantics.

## User Setup Required

None.

## Next Phase Readiness

Phase 05-03 can now consume one typed safety surface for homepage status, alert timeline, and mode-switch blockers.

## Self-Check: PASSED

- `pytest tests/unit/test_operator_safety.py -q` -> 4 passed.
- `pytest -q` -> 141 passed.
- Required `rg` checks for thresholds, `gap_fill`, `increase_exposure`, `preflight`, and `live-disabled` passed.

---
*Phase: 05-operator-console-safety-controls*
*Completed: 2026-04-22*
