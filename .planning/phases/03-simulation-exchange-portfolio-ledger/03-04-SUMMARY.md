---
phase: 03-simulation-exchange-portfolio-ledger
plan: 04
subsystem: portfolio-ledger
tags: [ledger, pnl, valuation, fees]
requires:
  - phase: 03-01
    provides: [CashLedgerEntry, PositionLedgerEntry, PositionState, ValuationSnapshot]
  - phase: 03-03
    provides: [SimulatedFill]
provides:
  - Cash and position ledger updates for paper fills
  - Separate fee accounting with Polymarket-style taker fee formula
  - Conservative mark policy and realized/unrealized PnL separation
affects: [paper-exchange, strategy-runtime, research-views]
tech-stack:
  added: []
  patterns: [pure ledger service with explicit accounting entries]
key-files:
  created:
    - src/polymarket_quant/services/portfolio_ledger.py
    - tests/unit/test_portfolio_ledger.py
  modified: []
key-decisions:
  - "Fill notional and fee are stored as separate cash ledger entries to avoid double-counting while preserving fee traceability."
  - "Long-token conservative mark uses best bid first, then last trade, then zero fallback."
patterns-established:
  - "LedgerUpdateResult groups cash, fee, and position entries produced by one fill."
requirements-completed: [SIM-03]
duration: 0 min
completed: 2026-04-19
---

# Phase 3 Plan 04: Portfolio Ledger Summary

**Cash, position, fee, realized PnL, unrealized PnL, and conservative valuation for simulated fills**

## Performance

- **Duration:** 0 min
- **Started:** 2026-04-19T00:00:00Z
- **Completed:** 2026-04-19T00:00:00Z
- **Tasks:** 4
- **Files modified:** 2

## Accomplishments

- Added `PortfolioLedgerService.apply_fill` for buy/sell cash and position entries.
- Added `PolymarketFeePolicy` with maker-zero and taker fee formula support.
- Added `ConservativeMarkPolicy`, `value_position`, and `apply_position_change`.
- Added tests covering fees, cash deltas, position deltas, realized PnL, unrealized PnL, and reward exclusion.

## Task Commits

1. **Tasks 1-4: Portfolio ledger** - `db20d07` (feat)

## Files Created/Modified

- `src/polymarket_quant/services/portfolio_ledger.py` - Ledger, fee, mark, and PnL service.
- `tests/unit/test_portfolio_ledger.py` - Accounting and valuation tests.

## Decisions Made

- Fee entries are separate cash ledger rows with reason `FEE`.
- `total_cash_delta` on `LedgerUpdateResult` is the sum of notional and fee deltas.
- Rewards remain out of core PnL in Phase 3.

## Deviations from Plan

- The plan wording described a single cash delta including fees plus a separate fee entry. Implementation separates notional and fee entries so stored cash ledger totals do not double-count fees.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Plan 03-05 can apply fills through the ledger service and return grouped accounting updates for paper exchange submissions.

## Self-Check: PASSED

- `pytest tests/unit/test_portfolio_ledger.py -q` -> 9 passed.
- `pytest -q` -> 105 passed.
- Required `rg` checks for mark policy and PnL terms passed.

---
*Phase: 03-simulation-exchange-portfolio-ledger*
*Completed: 2026-04-19*
