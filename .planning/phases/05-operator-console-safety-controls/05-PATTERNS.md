---
phase: 05-operator-console-safety-controls
status: complete
created: 2026-04-22
---

# Phase 5 Pattern Map

## Existing Patterns To Reuse

### UI contracts

Closest analogs:

- `src/polymarket_quant/ui/contracts.py`
- `tests/unit/test_market_universe_ui_contract.py`
- `tests/unit/test_market_data_ui_contract.py`

Pattern:

- Lock UI surface with explicit constants.
- Assert copy, layout regions, required sections, and out-of-scope exclusions in unit tests.
- Keep page modules thin and make helper functions directly testable.

Apply to:

- `src/polymarket_quant/ui/operator_console_app.py`
- `tests/unit/test_operator_console_ui_contract.py`

### Streamlit page shape

Closest analogs:

- `src/polymarket_quant/ui/market_universe_app.py`
- `src/polymarket_quant/ui/market_data_app.py`

Pattern:

- `main()` sets the page config and owns the top-level layout.
- Sidebar owns filters.
- DataFrame builders and filter helpers are separate functions.
- Timeline rendering is encapsulated in a dedicated helper.

Apply to:

- status-band helpers
- strategy overview dataframe builders
- console filter helpers
- alert timeline renderers

### Query-service boundary

Closest analog:

- `src/polymarket_quant/services/market_data_queries.py`

Pattern:

- Query service wraps one or more stores/readers.
- Return DataFrames or dict rows from explicit query methods rather than mixing SQL/IO into UI code.
- Keep read-side transformations isolated and deterministic.

Apply to:

- `src/polymarket_quant/services/operator_queries.py`

### Store and persistence access

Closest analogs:

- `src/polymarket_quant/storage/market_data_store.py`
- `src/polymarket_quant/storage/simulation_store.py`

Pattern:

- `dsn` or fake `connection` injection.
- Store methods expose factual reads and writes, not UI assumptions.
- Unit tests prefer fake connections/stores instead of requiring live PostgreSQL.

Apply to:

- runtime heartbeat/state registry
- any run-state persistence or operator-state write path

### Orchestration/service boundaries

Closest analogs:

- `src/polymarket_quant/services/strategy_cli.py`
- `src/polymarket_quant/services/paper_exchange.py`

Pattern:

- Inject collaborators via constructors.
- Orchestration services assemble multiple lower-level components without collapsing domain boundaries.
- Results should be structured objects, not ad hoc dicts, when control decisions matter.

Apply to:

- mode preflight service
- safety control/or alert derivation services
- runtime state registry integration

### Timeline/event style

Closest analogs:

- `src/polymarket_quant/services/market_sync.py`
- `src/polymarket_quant/services/backfill.py`
- `src/polymarket_quant/services/realtime_collector.py`

Pattern:

- Event/timeline rows use concise status labels and clear source markers.
- Status/event streams are operator-facing facts, not raw stack traces.
- Retry/failure/started/completed states are explicit.

Apply to:

- alert timeline rows
- preflight result summaries
- mode switch event entries
- runtime heartbeat/state-change events

## Suggested File Ownership By Plan

| Plan | Primary Files | Closest Analog |
|------|---------------|----------------|
| 05-01 | `domain/operator.py`, `services/operator_runtime_registry.py`, runtime integrations, tests | `domain/strategy.py`, `strategy_cli.py` |
| 05-02 | `services/operator_safety.py`, tests | `order_risk.py`, `paper_exchange.py` |
| 05-03 | `services/operator_queries.py`, tests | `market_data_queries.py`, `simulation_store.py` |
| 05-04 | `ui/contracts.py`, `ui/operator_console_app.py`, UI contract tests | `market_universe_app.py`, `market_data_app.py` |
| 05-05 | docs, exports, console integration tests | `strategy_cli.py`, README/documented run paths |

## Landmines

- Do not infer `running` or `last heartbeat` purely from completed run artifacts.
- Do not place alert/blocking logic inside Streamlit widgets.
- Do not make the homepage tab-first; the locked layout is single-page with local toggles.
- Do not bypass preflight or explicit confirmation for mode changes.
- Do not introduce a true live mode, wallet/auth workflow, or any implication that live execution is available.
- Do not block exposure-reducing actions when critical expiry rules only intend to block new exposure.
- Do not let filter state drift per widget; the user explicitly wants shared filters across table and timeline.

## PATTERN MAPPING COMPLETE
