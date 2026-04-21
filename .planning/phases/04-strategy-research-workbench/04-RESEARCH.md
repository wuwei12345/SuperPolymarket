---
phase: 04-strategy-research-workbench
status: complete
researched_at: 2026-04-21
sources_checked: local_codebase, planning_artifacts
---

# Phase 4 Research: Strategy Research Workbench

## Research Goal

Answer what the planner needs to know to build Phase 4 well: a strategy runtime that reuses the same strategy class across replay backtest and realtime paper modes, preserves the alpha -> sizing -> execution split, and emits reproducible run artifacts that are explainable after the fact.

## Source-Backed Facts

### Existing simulator boundary

- Phase 2 already provides normalized public market data, replay-oriented latest-state queries, price series queries, and explicit `gap_fill` / source markers.
- Phase 3 already provides a stable `PaperExchangeService.submit_order_intent` boundary that converts execution decisions into risk decisions, orders, fills, ledger updates, and valuation facts.
- The current codebase already uses Pydantic v2 domain objects, injectable service classes, and fake-store unit tests instead of live integration tests for core behavior.

### Current stack gaps relevant to Phase 4

- `pyproject.toml` currently includes `httpx`, `pydantic`, `psycopg`, `tenacity`, `streamlit`, `pandas`, and `websockets`, but it does not yet include a YAML parser or a parquet-oriented dependency such as `pyarrow`.
- Project-wide stack research already recommends Parquet + DuckDB for reproducible research storage, but that recommendation has not yet been wired into runtime code or dependencies.
- There is no existing strategy runtime module, strategy base class, signal model, run manifest writer, experiment bundle writer, or CLI entry point for replay/paper execution.

### Locked product constraints

- Strategies must be Python classes with `on_init`, `on_event`, `on_clock`, and `on_finish`.
- Strategies emit target-based `Signal`, not `OrderIntent`.
- Runtime remains event-driven in all modes, but Phase 4 only needs time-based fixed-step support first.
- Every run must generate a `Run Manifest + Artifacts Bundle` with resolved config, data scope, execution evidence, metrics, and logs.

## Implementation Guidance

### Strategy contract and runtime shape

Use a dedicated Phase 4 strategy domain module rather than extending `domain/simulation.py` directly.

Recommended symbols:

- `RunMode`: `REPLAY`, `REALTIME_PAPER`, `RESEARCH`
- `StrategyEventType`: `MARKET`, `EXECUTION`, `RISK`, `SYSTEM`
- `StrategySignal`
- `ResolvedRunConfig`
- `UniverseSnapshot`
- `RunManifest`
- `StrategyEvent`
- `StrategyContextSnapshot`
- `StrategySummary`

Recommended strategy boundary:

- `BaseStrategy` class with no-op lifecycle methods
- `on_init()` for loading run metadata and initializing local caches
- `on_event()` for event-driven updates and optional signal emission
- `on_clock()` for research-step decisions and the primary signal emission path
- `on_finish()` for summary/debug hooks

Keep the strategy contract mode-agnostic. Replay and realtime runners should adapt the feed source and clock semantics, not force strategy-specific branching.

### Context and event model

The runtime context should be explicit and typed. The `ctx` object should carry:

- current market/token snapshot
- feature snapshot
- current portfolio state (positions, cash, open orders)
- recent fills and recent risk decisions
- run metadata and active time window

Keep events small and append-only:

- market events should identify source token/condition/time
- execution events should carry order/fill/cancel/replace updates
- risk events should carry structured `RiskDecision`
- system events should carry lifecycle signals such as warmup complete or end-of-run

### Replay runner

Replay should remain event-driven underneath, even when fixed-step strategy decisions are enabled.

Recommended behavior:

- read normalized market data in event order
- feed all source events through `on_event()`
- maintain a separate clock that triggers `on_clock()` on configured time boundaries
- ensure no future data leaks into the current decision step
- mark repaired or gap-filled data in context so strategy/debug artifacts can explain data quality

Phase 4 should only implement time-based stepping first, such as `1s`, `5s`, or `1m`.

### Signal -> sizing -> execution boundary

Do not let strategies submit `OrderIntent` directly.

Recommended layering:

1. strategy emits target-based `StrategySignal`
2. a sizing/portfolio adapter converts target state into desired delta
3. an execution adapter converts desired delta into `OrderIntent`
4. `PaperExchangeService` handles risk, lifecycle, fills, and accounting

This keeps signal research, sizing policy, and execution behavior swappable.

### Run artifacts and storage

Artifact storage should be file-system first for Phase 4, with one directory per run:

- `manifest.json`
- `signals.parquet`
- `order_intents.parquet`
- `orders.parquet`
- `fills.parquet`
- `positions.parquet`
- `cash_ledger.parquet`
- `pnl_timeline.parquet`
- `risk_decisions.parquet`
- `metrics.json` or `metrics.parquet`
- `strategy.log`
- `framework.log`

Persist resolved config values, not just config paths.

DuckDB is a good read/query companion for local experiment analysis, but the artifact bundle itself should stay as explicit files so runs remain portable and inspectable without a database dependency.

### Dependency implications

Phase 4 likely needs:

- `PyYAML` for YAML config support
- `pyarrow` for deterministic parquet writing via pandas or Arrow APIs
- `duckdb` for local analysis and comparison workflows

These should be added deliberately with unit-test coverage, not opportunistically at CLI time.

### Metrics and explainability

Metrics should derive from strategy outputs and execution facts, not from ad hoc log parsing.

Minimum computed metrics:

- total return
- realized and unrealized pnl
- turnover
- fill rate
- cancel rate
- average holding time
- max drawdown
- exposure peak
- reject count
- slippage metrics

Keep metrics computation as a separate service so replay runs and realtime paper runs share one summary implementation.

## Validation Architecture

Phase 4 can be validated primarily with deterministic unit tests and temporary run directories. No live Polymarket API or live PostgreSQL is required for the main feedback loop.

Required automated checks:

- `pytest tests/unit/test_strategy_models.py -q`
- `pytest tests/unit/test_run_artifacts.py -q`
- `pytest tests/unit/test_replay_runtime.py -q`
- `pytest tests/unit/test_signal_execution.py -q`
- `pytest tests/unit/test_strategy_cli.py -q`
- `pytest -q`

Required grep checks:

- `rg "class StrategySignal|class RunManifest|class ResolvedRunConfig" src/polymarket_quant/domain/strategy.py`
- `rg "class BaseStrategy|def on_init|def on_event|def on_clock|def on_finish" src/polymarket_quant/strategy/base.py`
- `rg "manifest.json|to_parquet|strategy.log|framework.log" src/polymarket_quant/services/run_artifacts.py`
- `rg "PaperExchangeService|target_exposure|target_position" src/polymarket_quant/services/signal_execution.py`
- `rg "yaml|json|replay|realtime_paper" src/polymarket_quant/services/strategy_cli.py`

## Planning Implications

- Put strategy contract, signal model, and run config types first.
- Add artifact bundle writing before the full runtime so every later plan can produce reproducible outputs.
- Build replay runtime before realtime paper mode, because replay is the lower-risk path for validating strategy semantics.
- Keep signal-to-execution translation separate from strategy logic and from `PaperExchangeService`.
- Finish with CLI/config/metrics wiring so the phase ships as a usable research surface rather than a pile of internal helpers.

## External Sources

None required beyond already captured local planning artifacts. Phase 4 planning is constrained mainly by locked project decisions and the verified local substrate from Phases 2 and 3.

## RESEARCH COMPLETE
