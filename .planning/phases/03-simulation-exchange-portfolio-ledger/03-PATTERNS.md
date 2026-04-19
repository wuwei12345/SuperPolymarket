---
phase: 03-simulation-exchange-portfolio-ledger
status: complete
created: 2026-04-19
---

# Phase 3 Pattern Map

## Existing Patterns To Reuse

### Domain models

Closest analogs:

- `src/polymarket_quant/domain/market.py`
- `src/polymarket_quant/domain/market_data.py`

Pattern:

- Pydantic v2 models.
- `model_config = ConfigDict(extra="forbid")`.
- Explicit validators reject blank identifiers.
- Decimal fields are used for market prices, sizes, and quantities.

Apply to:

- `src/polymarket_quant/domain/simulation.py`
- `tests/unit/test_simulation_models.py`

### PostgreSQL store

Closest analogs:

- `src/polymarket_quant/storage/postgres_schema.sql`
- `src/polymarket_quant/storage/market_data_store.py`
- `tests/unit/test_market_data_store.py`

Pattern:

- Keep schema SQL in one file loaded by store `init_schema()`.
- Accept `dsn` or injectable fake `connection`.
- Use `_execute`, `_executemany`, `_fetch_all`, `_adapt_params`, and JSONB adaptation helpers.
- Unit tests assert SQL text and fake connection calls instead of requiring live PostgreSQL.

Apply to:

- Extend `src/polymarket_quant/storage/postgres_schema.sql`.
- Create `src/polymarket_quant/storage/simulation_store.py`.
- Create `tests/unit/test_simulation_store.py`.

### Service boundaries

Closest analogs:

- `src/polymarket_quant/services/backfill.py`
- `src/polymarket_quant/services/realtime_collector.py`
- `src/polymarket_quant/services/market_data_queries.py`

Pattern:

- Service classes accept store/client dependencies in constructors.
- Deterministic pure helpers are kept close to the service.
- Results/events are typed objects and are testable with fake stores.
- CLI entry points are optional and use `if __name__ == "__main__":`.

Apply to:

- `src/polymarket_quant/services/order_lifecycle.py`
- `src/polymarket_quant/services/order_risk.py`
- `src/polymarket_quant/services/fill_engine.py`
- `src/polymarket_quant/services/portfolio_ledger.py`
- `src/polymarket_quant/services/paper_exchange.py`

### Query and UI boundary

Closest analog:

- `src/polymarket_quant/services/market_data_queries.py`

Pattern:

- Query services wrap store reads.
- UI does not directly call Polymarket clients.
- Phase 3 does not need a new UI, but final service should expose read/query methods that Phase 5 can use.

Apply to:

- `SimulationStore.fetch_orders`
- `SimulationStore.fetch_positions`
- `SimulationStore.fetch_pnl`

## Suggested File Ownership By Plan

| Plan | Primary Files | Closest Analog |
|------|---------------|----------------|
| 03-01 | `domain/simulation.py`, `storage/simulation_store.py`, `postgres_schema.sql` | `domain/market_data.py`, `storage/market_data_store.py` |
| 03-02 | `services/order_lifecycle.py`, `services/order_risk.py` | service classes and fake-store tests |
| 03-03 | `services/fill_engine.py` | `services/backfill.py` normalization helpers |
| 03-04 | `services/portfolio_ledger.py` | store + query service pattern |
| 03-05 | `services/paper_exchange.py`, README, exports | service orchestration patterns |

## Landmines

- Do not mutate Phase 1 SQLite `MarketStore`; Phase 3 should read token/reference state from Phase 2 PostgreSQL reference data or injected metadata.
- Do not rely on `last_trade_price` alone for fill simulation.
- Do not hide `gap_fill` source quality when using repaired data for fills or valuation.
- Do not merge rewards into realized/unrealized core PnL.
- Do not add live order authentication, wallet, or geoblock flows in Phase 3.

## PATTERN MAPPING COMPLETE
