---
phase: 03-simulation-exchange-portfolio-ledger
plan: 01
subsystem: simulation-storage
tags: [pydantic, postgres, ledger, risk, simulation]
requires:
  - phase: 02-historical-real-time-data-platform
    provides: [PostgreSQL schema pattern, market-data DTOs, store helper pattern]
provides:
  - Simulation domain models for orders, fills, ledger entries, valuation snapshots, and risk decisions
  - PostgreSQL `simulation` schema with order, fill, ledger, risk, and valuation tables
  - `SimulationStore` repository for Phase 3 services
affects: [phase-3-simulation, phase-4-strategy-runtime, phase-5-operator-console]
tech-stack:
  added: []
  patterns: [Pydantic v2 DTOs, PostgreSQL repository with injectable fake connection]
key-files:
  created:
    - src/polymarket_quant/domain/simulation.py
    - src/polymarket_quant/storage/simulation_store.py
    - tests/unit/test_simulation_models.py
    - tests/unit/test_simulation_store.py
  modified:
    - src/polymarket_quant/domain/__init__.py
    - src/polymarket_quant/storage/__init__.py
    - src/polymarket_quant/storage/postgres_schema.sql
key-decisions:
  - "Simulation facts are stored in a dedicated `simulation` schema instead of market-data tables."
  - "Risk decisions persist structured checks/reasons/warnings for later audit."
patterns-established:
  - "Simulation DTOs mirror Phase 2's strict Pydantic model style."
  - "SimulationStore mirrors MarketDataStore's injectable-connection test pattern."
requirements-completed: [SIM-01, SIM-03, RISK-01]
duration: 0 min
completed: 2026-04-19
---

# Phase 3 Plan 01: Simulation Data Foundation Summary

**Simulation order, fill, risk, ledger, and valuation contracts with isolated PostgreSQL storage**

## Performance

- **Duration:** 0 min
- **Started:** 2026-04-19T00:00:00Z
- **Completed:** 2026-04-19T00:00:00Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments

- Added strict Phase 3 Pydantic models for `OrderIntent`, `SimulatedOrder`, `SimulatedFill`, ledger entries, `ValuationSnapshot`, and `RiskDecision`.
- Extended `postgres_schema.sql` with a dedicated `simulation` schema and query views.
- Added `SimulationStore` with insert/upsert/fetch helpers and fake-connection unit coverage.

## Task Commits

1. **Tasks 1-3: Simulation models, schema, and store** - `7a98efd` (feat)

## Files Created/Modified

- `src/polymarket_quant/domain/simulation.py` - Phase 3 domain contracts and validation.
- `src/polymarket_quant/storage/simulation_store.py` - PostgreSQL repository for simulation records.
- `src/polymarket_quant/storage/postgres_schema.sql` - Added simulation tables and views.
- `tests/unit/test_simulation_models.py` - Model validation tests.
- `tests/unit/test_simulation_store.py` - Schema and repository contract tests.

## Decisions Made

- Used a separate `simulation` schema to keep execution facts away from market-data raw/normalized tables.
- Kept `OrderType.LIMIT` as the only P0 order type while allowing later services to model marketable limits via crossing logic.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required for unit-tested P0 behavior.

## Next Phase Readiness

Plan 03-02 can build lifecycle and risk services on top of `OrderIntent`, `SimulatedOrder`, and `RiskDecision`. Plan 03-03 can use `SimulatedFill` and book DTOs for fill simulation.

## Self-Check: PASSED

- `pytest tests/unit/test_simulation_models.py tests/unit/test_simulation_store.py -q` -> 14 passed.
- `pytest -q` -> 81 passed.
- Required `rg` checks for domain contracts, SQL objects, and store APIs passed.

---
*Phase: 03-simulation-exchange-portfolio-ledger*
*Completed: 2026-04-19*
