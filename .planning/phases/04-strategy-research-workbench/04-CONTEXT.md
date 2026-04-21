# Phase 4: Strategy Research Workbench - Context

**Gathered:** 2026-04-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 delivers the strategy runtime and experiment workbench for the simulator. It lets the same strategy logic run in replay backtest and realtime paper modes, while keeping strategy configuration, execution evidence, and experiment outputs reproducible and comparable across runs.

This phase builds on the Phase 2 market-data substrate and the Phase 3 paper exchange boundary. It does not add live trading, wallet/auth flows, operator console UX, or new exchange semantics beyond the already verified paper-execution contract.

</domain>

<decisions>
## Implementation Decisions

### Strategy contract
- **D-01:** Strategies must be implemented as Python classes, not as standalone function sets.
- **D-02:** The minimum strategy lifecycle contract is:
  - `on_init(self, ctx)` for loading parameters, universe, run metadata, and initializing internal state
  - `on_event(self, event, ctx)` for consuming Market / Execution / Risk / System events, updating state, and optionally emitting `Signal`
  - `on_clock(self, ts, ctx)` for fixed-step decisions in research mode and the primary recommended place to emit `Signal`
  - `on_finish(self, ctx)` for summary/debug output and cleanup
- **D-03:** The strategy class must be able to own metadata, parameters, internal caches, indicator state, lifecycle hooks, and strategy-specific debug output.

### Signal and execution separation
- **D-04:** Strategies must emit `Signal`, not `OrderIntent`, as their primary output.
- **D-05:** Phase 4 must keep three layers separate: alpha (`Signal`), portfolio/sizing, and execution (`OrderIntent` / replace / cancel decisions).
- **D-06:** The first-class Phase 4 signal model is target-based, with `target_exposure` as the primary target semantic.
- **D-07:** `target_position` is an allowed secondary signal form, but not the primary semantic for Phase 4.
- **D-08:** The minimum signal payload is:
  - `token_id`
  - `target_exposure` (primary) or `target_position` (secondary)
  - `ts`
  - optional `reason_code`
  - optional `confidence`

### Runtime model
- **D-09:** The underlying framework must be event-driven in both replay and realtime paper operation.
- **D-10:** Research mode may additionally drive strategy decisions with a fixed time-step loop.
- **D-11:** For Phase 4, fixed-step research support is limited to time-based stepping first, not event-batch stepping.
- **D-12:** The same strategy contract should run in replay backtest and realtime paper mode, with the runtime adapting the data/feed source rather than forcing strategy rewrites.

### Strategy context contract
- **D-13:** The strategy `ctx` must include all of the following categories:
  - current market/token data
  - precomputed features
  - current positions, cash, and open/unfilled orders
  - recent fills and recent `RiskDecision` outputs
  - current run configuration and time-window context
- **D-14:** Context should be rich enough that replay and realtime paper can share the same strategy logic without ad hoc side-channel state injection.

### Run identity and reproducibility
- **D-15:** Every run must generate a `Run Manifest + Artifacts Bundle`.
- **D-16:** Each run must persist identity metadata:
  - `run_id`
  - `strategy_name`
  - `strategy_version`
  - `git_commit`
  - `start_time`
  - `end_time`
  - `mode` (`replay` / `realtime_paper` / `research`)
  - `environment` (`dev` / `staging` / `local`)
- **D-17:** Each run must persist a resolved configuration snapshot, not just config file paths. This includes:
  - strategy parameters
  - universe selection conditions
  - sizing configuration
  - execution configuration
  - risk limit configuration
  - replay window or realtime start settings
  - data-source configuration
- **D-18:** Each run must persist a data-scope snapshot including:
  - universe snapshot
  - token list
  - market / condition / yes-no token mappings
  - data window start and end
  - dataset version or dataset ID
  - whether `gap_fill` data is included
- **D-19:** Each run must persist execution evidence including:
  - signals
  - order intents
  - orders
  - fills
  - cancels / replaces
  - positions
  - cash ledger
  - pnl timeline
  - risk decisions
- **D-20:** Each run must persist summary metrics including:
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
- **D-21:** Each run must persist logs and debugging artifacts including:
  - strategy log
  - framework log
  - warnings
  - exceptions
  - sampled key feature snapshots
- **D-22:** The artifact bundle storage shape is one directory per run containing `manifest.json`, multiple `parquet` artifacts, and text log files.

### Entry points and configuration
- **D-23:** The primary user entry point for Phase 4 is CLI.
- **D-24:** The primary configuration format is YAML or JSON.
- **D-25:** A Python API is allowed as an auxiliary entry point, but it is not the primary Phase 4 operator workflow.

### Phase philosophy
- **D-26:** Phase 4 must not stop at "strategy code can run"; it must make every run explainable, reproducible, and comparable.

### the agent's Discretion
- Exact module layout for strategy base classes, context objects, and runtime orchestrators
- Exact naming of runtime modes, enums, and artifact files
- Exact parquet file split/partitioning scheme inside a run directory
- Exact shape of feature snapshot sampling and log formatting
- Exact typing approach for `ctx` and `Signal`, provided the locked semantics above remain intact

</decisions>

<specifics>
## Specific Ideas

- User explicitly wants the runtime to preserve a clean split between alpha, sizing/portfolio logic, and execution.
- The user's rationale for class-based strategies is that function-only strategies break down once state, warmup, multi-token caches, indicators, and shared replay/realtime context become non-trivial.
- `on_clock()` is the recommended primary signal-emission point in research mode, even though `on_event()` may also emit signals for event-driven strategies.
- The central product bar for Phase 4 is not merely "the strategy runs" but "the result can be explained, reproduced, and compared."

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition and project constraints
- `.planning/ROADMAP.md` — Phase 4 goal, requirements, and success criteria
- `.planning/REQUIREMENTS.md` — `STRAT-01`, `STRAT-02`, `STRAT-03`, and `OPS-02`
- `.planning/PROJECT.md` — simulation-first, Python-first, no-live-trading v1 constraints
- `.planning/STATE.md` — current project status and known replay/live risks

### Prior phase decisions that constrain Phase 4
- `.planning/phases/01-market-universe-metadata/01-CONTEXT.md` — active + accepting market-universe boundary and source-provenance expectations
- `.planning/phases/02-historical-real-time-data-platform/02-CONTEXT.md` — research-grade replay boundary, gap-fill/source markers, and top-N token universe shape
- `.planning/phases/02-historical-real-time-data-platform/02-VERIFICATION.md` — verified replay/data capabilities and DATA-04 scope note
- `.planning/phases/03-simulation-exchange-portfolio-ledger/03-CONTEXT.md` — locked paper-exchange semantics and `RiskDecision` boundary
- `.planning/phases/03-simulation-exchange-portfolio-ledger/03-VERIFICATION.md` — verified Phase 3 paper-execution behavior
- `.planning/phases/03-simulation-exchange-portfolio-ledger/03-05-SUMMARY.md` — `PaperExchangeService.submit_order_intent` as the stable execution boundary for strategies

### Architecture and product guidance
- `.planning/research/ARCHITECTURE.md` — strategy runtime boundary and upstream/downstream data flow
- `.planning/research/FEATURES.md` — research workflow expectations, experiment reproducibility, and anti-features
- `.planning/research/STACK.md` — Python, PostgreSQL, Parquet, and DuckDB direction for research/runtime work

### Existing implementation references
- `src/polymarket_quant/domain/market_data.py` — normalized market/token data models available to runtime context
- `src/polymarket_quant/domain/simulation.py` — order, fill, risk, position, and valuation models already established
- `src/polymarket_quant/services/paper_exchange.py` — stable paper execution boundary strategies should target via execution adapters
- `src/polymarket_quant/services/order_risk.py` — existing structured risk decision surface
- `src/polymarket_quant/storage/simulation_store.py` — current simulation persistence/query patterns
- `src/polymarket_quant/storage/postgres_schema.sql` — existing layered store and simulation schema conventions
- `README.md` — current public description of replay workflows and paper-exchange scope

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ReferenceToken`, `BookSnapshot`, `BestBidAsk`, and `LastTrade` already provide the canonical market-data inputs that strategy context should expose.
- Phase 3 already provides `OrderIntent`, `RiskDecision`, orders, fills, ledger entries, and valuation models, which Phase 4 should reuse instead of inventing parallel runtime models.
- `PaperExchangeService` is already the verified boundary for converting execution decisions into paper orders, fills, and ledger updates.
- `SimulationStore` and the PostgreSQL simulation schema provide a persistence starting point for execution evidence and runtime outputs.

### Established Patterns
- The codebase is Python-first with `src/` layout, Pydantic v2 models, and injectable service classes.
- Market data and simulation data are already modeled as explicit typed domain objects with `extra="forbid"`.
- Earlier phases prefer clear provenance, raw-vs-normalized separation, and replay/debug traceability over optimistic shortcuts.

### Integration Points
- Phase 4 should consume Phase 2 normalized market data and Phase 3 paper-exchange services, not bypass them.
- The runtime needs an adapter layer that converts target-based `Signal` into sizing and execution decisions before hitting `PaperExchangeService`.
- Experiment outputs need to bridge database-backed execution facts with per-run artifact bundles (`manifest.json` + parquet + logs).
- CLI/config entry points should resolve into the same runtime contract used by replay backtest and realtime paper runs.

</code_context>

<deferred>
## Deferred Ideas

- Event-batch fixed-step driving is deferred; Phase 4 fixed-step support starts with time-based stepping only.
- Live trading, wallet/auth handling, and operator console work remain outside this phase.
- Any attempt to collapse strategy alpha directly into `OrderIntent` emission is rejected for Phase 4 and should not be reintroduced as a shortcut.

</deferred>

---
*Phase: 04-strategy-research-workbench*
*Context gathered: 2026-04-21*
