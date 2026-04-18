---
phase: 02-historical-real-time-data-platform
plan: 02
subsystem: ingestion
tags: [polymarket, clob, rest, backfill, price-history, orderbook]
requires:
  - phase: 02-historical-real-time-data-platform
    provides: PostgreSQL MarketDataStore and market-data DTOs
provides:
  - CLOB REST client methods for batch price history, books, prices, and last trades
  - Data API raw trades/activity hooks
  - Ranked top-N token universe selector
  - REST backfill service for price history and current book snapshots
affects: [phase-02-realtime, phase-02-ui, phase-03-simulation]
tech-stack:
  added: []
  patterns: [raw-first REST ingestion, ranked token universe, Decimal-derived BBO]
key-files:
  created:
    - src/polymarket_quant/services/universe_selector.py
    - src/polymarket_quant/services/backfill.py
    - tests/unit/test_backfill.py
  modified:
    - src/polymarket_quant/adapters/polymarket.py
    - src/polymarket_quant/services/__init__.py
    - README.md
key-decisions:
  - "Selected top-N at token-row granularity, so Yes/No assets compete for the same configured token budget."
  - "Stored Data API trades/activity as optional raw hooks without making full ingestion a Phase 2 blocker."
patterns-established:
  - "Backfill writes raw REST payloads before normalized price/book/current-state rows."
  - "Book snapshots derive best bid, best ask, spread, midpoint, and last trade with Decimal math."
requirements-completed: [DATA-01, DATA-04]
duration: 28min
completed: 2026-04-18
---

# Phase 02 Plan 02: REST Backfill Summary

**Top-N token selection and CLOB REST backfill for price history, book snapshots, BBO, spread, midpoint, and last trade**

## Performance

- **Duration:** 28 min
- **Started:** 2026-04-18T11:02:00Z
- **Completed:** 2026-04-18T11:30:00Z
- **Tasks:** 4
- **Files modified:** 6

## Accomplishments

- Extended `ClobClient` with official CLOB batch endpoints for price history, books, prices, and last trade prices.
- Added `DataApiClient` raw hooks for future trades/activity calibration work.
- Added `UniverseSelector` that ranks Phase 1 active + accepting markets and emits Yes/No `ReferenceToken` rows.
- Implemented `MarketDataBackfillService` that writes raw price/book payloads before normalized points, book snapshots, BBO rows, and last trades.
- Documented the `python -m polymarket_quant.services.backfill` command and `POLYMARKET_TOP_N=50` default.

## Task Commits

1. **Wave 2 REST backfill tasks** - `f713d17` (feat)

## Files Created/Modified

- `src/polymarket_quant/adapters/polymarket.py` - Added CLOB batch market-data endpoints and Data API client.
- `src/polymarket_quant/services/universe_selector.py` - Top-N token selection from Phase 1 markets.
- `src/polymarket_quant/services/backfill.py` - REST backfill orchestration and CLI entrypoint.
- `tests/unit/test_backfill.py` - Adapter, selector, and backfill behavior tests.
- `README.md` - Added Phase 2 REST backfill docs.

## Decisions Made

- Used token count rather than market count for `top_n`, matching WebSocket subscription and normalized storage keys.
- Kept trades/activity optional as raw hooks to satisfy calibration extensibility without expanding Phase 2 scope.

## Deviations from Plan

Grouped the four tightly coupled REST backfill tasks into one commit because adapter, selector, service, and shared tests were developed together.

**Total deviations:** 1 procedural grouping deviation.
**Impact on plan:** No behavior changed; all Wave 2 acceptance criteria pass.

## Issues Encountered

None.

## User Setup Required

Live REST backfill requires `DATABASE_URL`, Phase 1 market data in `data/markets.sqlite3`, and public Polymarket API connectivity.

## Next Phase Readiness

WebSocket collection can reuse selected reference tokens and `MarketDataBackfillService` can be reused by gap-fill repair.

## Self-Check: PASSED

- `pytest tests/unit/test_backfill.py -q` passed.
- `pytest -q` passed with 49 tests.
- Required endpoint strings and service symbols were verified with `rg`.

---
*Phase: 02-historical-real-time-data-platform*
*Completed: 2026-04-18*
