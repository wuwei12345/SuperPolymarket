---
phase: 05-operator-console-safety-controls
status: complete
researched_at: 2026-04-22
sources_checked: local_codebase, planning_artifacts
---

# Phase 5 Research: Operator Console & Safety Controls

## Research Goal

Answer what the planner needs to know to build Phase 5 well: a conservative operator console that shows current system health and strategy status, derives alerts and new-order block state from factual runtime/market data, and supports preflight-gated mode switching without introducing any live-trading capability.

## Source-Backed Facts

### Existing operator-facing surface

- The codebase already uses Streamlit for internal operator/read-only pages in `market_universe_app.py` and `market_data_app.py`.
- Existing UI pages are table-first, use shared sidebar filters, and render bottom timelines with structured status rows instead of freeform log consoles.
- `ui/contracts.py` plus UI contract tests are already used to lock page copy, required fields, and out-of-scope exclusions.

### Existing data and execution substrate

- `MarketDataStore` already exposes `views.latest_market_state` and `views.price_series_recent`, which are directly usable for connection/liquidity/market health views.
- `SimulationStore` already exposes orders, transitions, fills, positions, PnL, and risk decisions through factual tables and query helpers.
- Phase 4 already added `RunArtifactBundleWriter`, `StrategyCliService`, and `ExperimentMetricsService`, so Phase 5 can read run manifests, parquet artifacts, and run summaries without inventing a new run format.

### Current gap that Phase 5 must close

- The current system has no explicit runtime heartbeat or status registry for `running / paused / error / blocked / last heartbeat`.
- Phase 4 artifacts primarily describe completed or persisted run outputs; they are not enough to infer live operator state during an active process.
- Therefore Phase 5 needs an explicit operator/runtime state layer rather than only reading historical artifacts.

### Mode-surface reality

- Phase 4 runtime modes are currently `replay`, `research`, and `realtime_paper`.
- Phase 5 product requirements define two distinct mode concepts:
  - global capability boundary: `replay`, `paper`, `live-disabled`
  - local strategy/run mode: what a specific strategy instance is actually doing
- `live-disabled` is a protective boundary only. v1 still does not implement live trading, auth, or wallet flows.

## Implementation Guidance

### Runtime state and heartbeat model

Introduce explicit operator-facing state models and a registry/service for:

- global mode
- connection health
- strategy/run status
- last heartbeat timestamp
- summarized new-order block status
- latest alert summary

This should be written by runtime code paths, not inferred only from completed manifests.

Recommended design:

- domain-level operator models in a dedicated module
- a registry/service that can be dependency-injected into `StrategyCliService` and realtime runners
- read-side query methods that summarize current state for the UI

### Safety-control boundary

Keep blocking and alert logic outside Streamlit code.

Recommended split:

1. input facts from latest market state, connection status, global mode, and runtime positions/orders
2. alert derivation service for `Info / Warning / Critical`
3. new-order gate service for `allowed / partially blocked / fully blocked`
4. mode-preflight service for explicit switch validation

This preserves the conservative fail-safe semantics the user locked and keeps UI rendering simple.

### Expiry and liquidity logic

Expiry and liquidity rules are multi-threshold and asymmetric:

- warning states should surface operator awareness
- critical states should block new exposure
- critical expiry must still allow `reduce`, `close`, and other risk-release actions

That asymmetry strongly suggests a structured decision object rather than a plain boolean.

### Query layer for the console

The console needs a dedicated query/aggregation layer rather than direct calls from Streamlit into stores and parquet files.

Recommended responsibilities:

- load manifests and artifact summaries from run directories
- join factual simulation state with latest market state
- group by `strategy`, `market`, `event`, and `time window`
- expose homepage-ready datasets:
  - status band snapshot
  - strategy overview rows
  - positions/orders detail
  - pnl/exposure detail
  - alerts/event timeline
  - runs/artifacts listing

This query layer is also the right place to derive Phase 5-only metrics such as grouped win rate if Phase 4 run summaries do not already carry it.

### UI architecture

Stay with Streamlit for this phase.

Recommended shape:

- new `operator_console_app.py`
- reuse sidebar filters and table/timeline helpers already established in earlier UI modules
- single-page layout with local toggles, not tab-first
- fixed status band at the top
- top overview table grouped by strategy
- bottom event timeline
- two default detail panes only:
  - `Positions / Orders`
  - `PnL / Exposure`

`Runs / Artifacts` should exist as a secondary page or secondary section, not a homepage-default detail pane.

### Mode switching

Mode switching should be modeled as:

- preflight evaluation
- explicit human confirmation
- only then state mutation

Do not let the UI directly mutate mode without a preflight result object. This is especially important because `live-disabled` is a protective boundary and must never be treated as a regular execution path.

## Validation Architecture

Phase 5 can stay mostly deterministic and unit-testable.

Recommended automated checks:

- `pytest tests/unit/test_operator_models.py -q`
- `pytest tests/unit/test_operator_safety.py -q`
- `pytest tests/unit/test_operator_queries.py -q`
- `pytest tests/unit/test_operator_console_ui_contract.py -q`
- `pytest tests/unit/test_operator_console.py -q`
- `pytest -q`

Recommended grep checks:

- `rg "Critical|Warning|Info|last_heartbeat|global_mode" src/polymarket_quant/domain src/polymarket_quant/services`
- `rg "spread|top_of_book_depth_usdc|gap_fill|increase_exposure" src/polymarket_quant/services/operator_safety.py`
- `rg "strategy|market|event|time_window|win_rate" src/polymarket_quant/services/operator_queries.py`
- `rg "Operator Console|last heartbeat|Runs / Artifacts|preflight|live-disabled" src/polymarket_quant/ui README.md`

Manual smoke checks should focus on layout and operator readability, not on data correctness already covered by unit tests.

## Planning Implications

- Build explicit operator state/heartbeat models first, because the console cannot honestly show `running / blocked / last heartbeat` without them.
- Build safety/alert/preflight logic before the main console page so UI can render real state rather than placeholders.
- Add a dedicated query layer before the Streamlit page to keep the UI thin and testable.
- Build the homepage before runs/artifacts polish, because the homepage carries the core Phase 5 success criteria.
- Finish with mode-switch confirmation flow, docs, and exports so the phase ships as an operator workflow rather than just another read-only monitor.

## External Sources

No external research was required beyond the already captured local planning artifacts and verified codebase boundaries. Phase 5 planning is primarily constrained by existing Streamlit/UI patterns, Phase 3 risk facts, and Phase 4 runtime/artifact behavior.

## RESEARCH COMPLETE
