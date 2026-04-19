---
phase: 03-simulation-exchange-portfolio-ledger
plan: 02
subsystem: order-risk
tags: [risk, orders, lifecycle, pydantic]
requires:
  - phase: 03-01
    provides: [OrderIntent, SimulatedOrder, RiskDecision]
provides:
  - Deterministic order lifecycle transition service
  - Structured hard and warning risk checks
affects: [paper-exchange, strategy-runtime, operator-console]
tech-stack:
  added: []
  patterns: [structured RiskDecision outputs, lifecycle transition guards]
key-files:
  created:
    - src/polymarket_quant/services/order_lifecycle.py
    - src/polymarket_quant/services/order_risk.py
    - tests/unit/test_order_risk.py
  modified: []
key-decisions:
  - "Hard risk reasons use machine-readable codes for balance, size, tick, order, market, and token limits."
  - "Portfolio/event/drawdown/liquidity checks emit warnings unless a hard rejection is present."
patterns-established:
  - "Lifecycle transitions are encoded centrally and invalid transitions raise deterministic ValueError messages."
requirements-completed: [SIM-01, RISK-01]
duration: 0 min
completed: 2026-04-19
---

# Phase 3 Plan 02: Order Lifecycle and Risk Summary

**Risk-first order lifecycle with hard rejects, warnings, and deterministic state transitions**

## Performance

- **Duration:** 0 min
- **Started:** 2026-04-19T00:00:00Z
- **Completed:** 2026-04-19T00:00:00Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Added `OrderLifecycleService` for legal order state transitions, cancel, replace, reject, open, partial fill, and fill states.
- Added `RiskLimits`, `MarketConstraints`, `validate_order_intent`, and `apply_risk_checks`.
- Covered hard reject precedence and warning-only aggregate checks with unit tests.

## Task Commits

1. **Tasks 1-3: Order lifecycle and risk checks** - `f72bcbe` (feat)

## Files Created/Modified

- `src/polymarket_quant/services/order_lifecycle.py` - Central state transition service.
- `src/polymarket_quant/services/order_risk.py` - Structured pre-trade risk checks.
- `tests/unit/test_order_risk.py` - Lifecycle and risk decision coverage.

## Decisions Made

- Risk warnings are preserved even when the final decision is a hard `REJECT`.
- Lifecycle methods return both the updated order and transition fact so persistence can stay audit-friendly.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 03-05 can call `apply_risk_checks` before order acceptance and persist structured `RiskDecision` outputs. Cancel and replace orchestration can delegate to `OrderLifecycleService`.

## Self-Check: PASSED

- `pytest tests/unit/test_order_risk.py -q` -> 7 passed.
- `pytest -q` -> 88 passed.
- Required `rg` checks for risk and lifecycle APIs passed.

---
*Phase: 03-simulation-exchange-portfolio-ledger*
*Completed: 2026-04-19*
