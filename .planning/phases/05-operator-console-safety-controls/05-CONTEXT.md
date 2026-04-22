# Phase 5: Operator Console & Safety Controls - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 5 delivers the operator-facing control surface and safety-control layer for the simulator. It gives the user a single console to see system health, strategy/run status, orders, positions, PnL, exposure, and alerts, while enforcing conservative new-order guardrails and explicit mode-switch protections.

This phase builds on the Phase 4 runtime, metrics, and artifact bundle model. It does not introduce live trading, wallet/auth flows, alert acknowledgements, alert silencing, or a new strategy-runtime contract.

</domain>

<decisions>
## Implementation Decisions

### Operating principle
- **D-01:** Phase 5 should default to a conservative `fail-safe` posture rather than an aggressive `maximize trade` posture.
- **D-02:** Safety controls should prefer blocking new exposure when system state is uncertain, while still allowing exposure-reducing actions where explicitly approved.

### Console layout
- **D-03:** The console homepage uses a `single-page sectional layout with local toggles`, not a tab-first information architecture.
- **D-04:** The first screen must prioritize:
  - global mode
  - connection status
  - strategy status
  - alert summary
  - new-order block status
  - latest update time
- **D-05:** The top of the page should contain a fixed global status band using one or two rows of compact status cards.
- **D-06:** The global status band must include:
  - `Run Mode`: `replay` / `paper` / `live-disabled`
  - connection state for `DB`, market-data `WS`, execution layer, and risk layer
  - strategy status summary: `running` / `paused` / `error` / `blocked`
  - new-order status summary: `allowed` / `partially blocked` / `fully blocked`
  - high-priority alert count
  - latest update time
- **D-07:** The left side of the console remains a persistent shared filter rail rather than per-widget controls.
- **D-08:** Shared filters must include:
  - `strategy`
  - `market/event`
  - `token`
  - `time window`
  - `mode`
  - `severity`
  - `status` (`running` / `blocked` / `warning`)
- **D-09:** The homepage main area defaults to two major sections:
  - upper: strategy runtime overview
  - lower: alert / event timeline
- **D-10:** The default runtime overview table must aggregate by `strategy`.
- **D-11:** The strategy overview table should include:
  - `strategy name`
  - `mode`
  - `state`
  - `active positions`
  - `open orders`
  - `latest pnl`
  - `latest drawdown`
  - `alerts`
  - `new order status`
  - `last heartbeat`
- **D-12:** The homepage must include only two default detail blocks beyond the main table:
  - `Positions / Orders`
  - `PnL / Exposure`
- **D-13:** `Runs / Artifacts` should exist, but not as a homepage-default detail block.

### Metrics and aggregation views
- **D-14:** Phase 5 metrics and views must support aggregation by:
  - `strategy`
  - `market`
  - `event`
  - `time window`
- **D-15:** The default primary lens is `strategy`, not market or event.
- **D-16:** The homepage core metrics should emphasize:
  - `pnl`
  - `drawdown`
  - `exposure`
  - `turnover`
  - `alerts`
  - `open positions`
  - `open orders`

### Alerting and timeline
- **D-17:** The console must present both:
  - current-state summaries
  - a traceable event timeline
- **D-18:** The default lower section on the homepage should show recent event flow rather than raw log text.
- **D-19:** Alert severity levels are:
  - `Critical`
  - `Warning`
  - `Info`
- **D-20:** Phase 5 alert timeline is read-only. Acknowledge, mute, or silence actions are deferred.

### Mode model and switching
- **D-21:** Mode is modeled at two layers:
  - global mode
  - strategy/run local mode
- **D-22:** Global mode controls the system-wide maximum capability boundary.
- **D-23:** Global mode options are:
  - `replay`
  - `paper`
  - `live-disabled`
- **D-24:** Strategy/run mode describes how an individual strategy instance or run is currently operating.
- **D-25:** The console UI must clearly distinguish global mode from strategy/run mode to avoid operator confusion.
- **D-26:** Any mode switch must execute a preflight check before the change is accepted.
- **D-27:** Any mode switch must require explicit human confirmation after preflight results are shown.
- **D-28:** `live-disabled` remains a disabled capability boundary in v1, not a real live-trading mode.

### Hard new-order blocking
- **D-29:** Hard blocks must reject new exposure-increasing orders immediately.
- **D-30:** The following conditions are hard blockers for new orders:
  - market closed
  - market not accepting orders
  - mode unavailable
  - critical connection incompleteness / key dependency outage
  - severe near-expiry state
  - severe liquidity shortage
- **D-31:** In severe near-expiry conditions, the system must still allow:
  - `reduce`
  - `close`
  - explicit risk-release orders
- **D-32:** In severe near-expiry conditions, the system must block new exposure-increasing behavior.

### Expiry-based safety thresholds
- **D-33:** Expiry thresholds are tiered as:
  - `Info`: time to expiry `< 120 minutes`
  - `Warning`: time to expiry `< 60 minutes`
  - `Critical`: time to expiry `< 15 minutes`
- **D-34:** `Info` expiry state is display-only and should not produce an alert by itself.
- **D-35:** `Warning` expiry state raises an alert but does not automatically block new orders.
- **D-36:** `Critical` expiry state blocks new exposure-increasing orders by default.

### Liquidity and market-quality thresholds
- **D-37:** Liquidity quality decisions must consider all of:
  - spread
  - top-of-book depth
  - recent activity
  - book completeness
- **D-38:** A `Warning` liquidity condition should be raised when any of the following holds:
  - `spread > max(3 ticks, 3%)`
  - `top_of_book_depth_usdc < 2 x min_order_size`
  - no recent trades in the last `5 minutes`
  - single-sided book failure (`bid` or `ask` missing)
- **D-39:** A `Critical` liquidity condition should be raised when any of the following holds:
  - `spread > max(5 ticks, 5%)`
  - `top_of_book_depth_usdc < 1 x min_order_size`
  - no recent trades in the last `15 minutes`
  - repeated `gap_fill` / snapshot instability above roughly `>3 times per minute`
  - severe book abnormality, including missing sides or strong imbalance
- **D-40:** `Warning` liquidity state should alert first without automatically blocking.
- **D-41:** `Critical` liquidity state should hard-block new exposure-increasing orders.

### Additional warning-only conditions
- **D-42:** The following conditions should begin as warning-only signals rather than hard blocks:
  - general near-expiry state
  - non-critical liquidity weakness
  - frequent `gap_fill`
  - abnormal `drawdown`
  - abnormal `turnover`

### the agent's Discretion
- Exact Streamlit component structure, provided the page preserves the single-page sectional hierarchy above.
- Exact card styling, iconography, and compact status visual language.
- Exact wording and formatting of preflight result summaries.
- Exact implementation details for market-quality scoring, provided the locked thresholds and conservative semantics remain intact.
- Exact secondary-page structure for `Runs / Artifacts`, as long as it stays out of the homepage-default detail blocks.

</decisions>

<specifics>
## Specific Ideas

- The homepage should answer “is anything broken or dangerous right now?” before it answers “how is performance?”
- Shared filters are not decorative; they exist so every table and timeline on the page stays aligned to the same operating slice.
- The homepage should feel like a control console, not a notebook or analytics tab set.
- The event timeline should prefer interpretable operational events over raw log dumps.
- In critical expiry conditions, the system should prioritize risk release over trade opportunity.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition and operator goals
- `.planning/ROADMAP.md` — Phase 5 goal, requirements, success criteria, and UI expectation
- `.planning/REQUIREMENTS.md` — `RISK-02`, `RISK-03`, `OPS-01`, and `OPS-03`
- `.planning/PROJECT.md` — simulation-first, no-live-trading-v1, and event-driven system constraints
- `.planning/STATE.md` — current project status and known project risks

### Prior phase constraints
- `.planning/phases/01-market-universe-metadata/01-CONTEXT.md` — table-first UI, filter behavior, and source-traceability expectations
- `.planning/phases/02-historical-real-time-data-platform/02-CONTEXT.md` — gap-fill semantics, replay-quality boundaries, and data-health signals
- `.planning/phases/03-simulation-exchange-portfolio-ledger/03-CONTEXT.md` — `RiskDecision`, exposure limits, and hard-reject semantics
- `.planning/phases/04-strategy-research-workbench/04-CONTEXT.md` — unified run modes, artifact bundle contract, and experiment metrics expectations

### Existing implementation references
- `src/polymarket_quant/services/order_risk.py` — existing structured risk checks and `RiskDecision` surface
- `src/polymarket_quant/services/paper_exchange.py` — execution boundary that Phase 5 monitors rather than replaces
- `src/polymarket_quant/services/strategy_cli.py` — current mode/config/runtime entry surface
- `src/polymarket_quant/services/experiment_metrics.py` — current run-summary metrics contract
- `src/polymarket_quant/ui/market_universe_app.py` — existing table-first, filter-left, timeline-bottom UI pattern
- `src/polymarket_quant/ui/market_data_app.py` — existing monitor-style table plus line-chart plus timeline pattern
- `README.md` — current public description of phase boundaries and runtime surface

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RiskDecision` and pre-trade risk services already exist and can be surfaced in the console rather than reinvented.
- `StrategyCliService` already defines the Phase 4 runtime surface for `replay`, `research`, and `realtime_paper`.
- `ExperimentMetricsService` already computes summary metrics that Phase 5 can aggregate and display.
- Existing Streamlit apps already establish sidebar filters, table-first layout, and expandable timeline sections.

### Established Patterns
- The project already prefers Streamlit for operator-facing pages.
- Existing UI work favors left-side filters, wide data tables, concise status captions, and bottom timelines over card-heavy navigation.
- Runtime and execution services are already separated; Phase 5 should observe and control them, not collapse them together.

### Integration Points
- Phase 5 should read Phase 4 manifests, metrics summaries, and artifact bundles for run-level observability.
- Phase 5 should surface Phase 3 risk decisions, paper-order states, fills, positions, and exposure facts.
- Mode preflight should attach to the existing Phase 4 runtime entry path rather than introducing a separate execution path.
- Liquidity and expiry guardrails should build on Phase 2 market data and normalized latest-state queries.

</code_context>

<deferred>
## Deferred Ideas

- Alert acknowledgement, muting, and silence controls
- Any real live-trading enablement or wallet/auth management
- Additional homepage detail panes beyond `Positions / Orders` and `PnL / Exposure`
- Promotion of warning-only conditions into hard blocks beyond the locked conservative defaults

</deferred>

---
*Phase: 05-operator-console-safety-controls*
*Context gathered: 2026-04-22*
