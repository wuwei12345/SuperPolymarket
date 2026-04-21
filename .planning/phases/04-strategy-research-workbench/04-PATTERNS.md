---
phase: 04-strategy-research-workbench
status: complete
created: 2026-04-21
---

# Phase 4 Pattern Map

## Existing Patterns To Reuse

### Domain models

Closest analogs:

- `src/polymarket_quant/domain/market_data.py`
- `src/polymarket_quant/domain/simulation.py`

Pattern:

- Pydantic v2 models.
- `model_config = ConfigDict(extra="forbid")`.
- Explicit validators for identifiers and value ranges.
- Domain objects are serializable via `model_dump(mode="json")`.

Apply to:

- `src/polymarket_quant/domain/strategy.py`
- `tests/unit/test_strategy_models.py`

### Service boundaries

Closest analogs:

- `src/polymarket_quant/services/market_data_queries.py`
- `src/polymarket_quant/services/backfill.py`
- `src/polymarket_quant/services/paper_exchange.py`

Pattern:

- Services accept dependencies via constructor injection.
- Pure transformation helpers stay near services and are easy to unit test.
- Results are typed objects instead of loose dicts where behavior matters.

Apply to:

- `src/polymarket_quant/services/run_artifacts.py`
- `src/polymarket_quant/services/replay_runtime.py`
- `src/polymarket_quant/services/signal_execution.py`
- `src/polymarket_quant/services/experiment_metrics.py`
- `src/polymarket_quant/services/strategy_cli.py`

### PostgreSQL and storage access

Closest analogs:

- `src/polymarket_quant/storage/market_data_store.py`
- `src/polymarket_quant/storage/simulation_store.py`

Pattern:

- `dsn` or fake `connection` injection.
- SQL schema remains centralized in `postgres_schema.sql`.
- Unit tests assert behavior with fake connections instead of requiring live PostgreSQL.

Apply to:

- Any Phase 4 persistence helper that needs database reads for execution facts
- Any future run index or experiment metadata store

### Query/report boundary

Closest analog:

- `src/polymarket_quant/services/market_data_queries.py`

Pattern:

- Query services wrap store reads.
- DataFrame builders live near query/report services.
- UI or CLI should not talk directly to low-level stores when a stable query boundary helps.

Apply to:

- metrics/report services
- run summary readers
- artifact comparison helpers

### CLI and entry points

Closest analogs:

- `src/polymarket_quant/services/backfill.py`
- `src/polymarket_quant/services/realtime_collector.py`

Pattern:

- Main entry point lives in a service module or a thin CLI wrapper.
- Environment resolution is explicit.
- Long-running behavior is encapsulated in classes instead of script-only logic.

Apply to:

- `src/polymarket_quant/services/strategy_cli.py`

## Suggested File Ownership By Plan

| Plan | Primary Files | Closest Analog |
|------|---------------|----------------|
| 04-01 | `domain/strategy.py`, `strategy/base.py`, tests | `domain/market_data.py`, `domain/simulation.py` |
| 04-02 | `services/run_artifacts.py`, dependency updates, tests | `services/market_data_queries.py`, store serialization patterns |
| 04-03 | `services/strategy_runtime.py`, `services/replay_runtime.py`, tests | `services/backfill.py`, `services/realtime_collector.py` |
| 04-04 | `services/signal_execution.py`, `services/realtime_strategy_runner.py`, tests | `services/paper_exchange.py` orchestration |
| 04-05 | `services/experiment_metrics.py`, `services/strategy_cli.py`, README, exports, tests | query service + CLI orchestration patterns |

## Landmines

- Do not let strategies emit `OrderIntent` directly; this collapses alpha, sizing, and execution layers.
- Do not create separate replay-only and realtime-only strategy interfaces.
- Do not store only config file paths; persist resolved config values.
- Do not compute run metrics from logs when factual execution evidence already exists.
- Do not lose `gap_fill` and data-version context in replay artifacts; reproducibility depends on it.
- Do not bypass `PaperExchangeService` for paper execution in realtime mode.

## PATTERN MAPPING COMPLETE
