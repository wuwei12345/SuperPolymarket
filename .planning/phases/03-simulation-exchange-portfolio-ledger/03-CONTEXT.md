# Phase 3: Simulation Exchange & Portfolio Ledger - Context

**Gathered:** 2026-04-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 3 delivers a Polymarket-style paper exchange and portfolio ledger. It converts strategy order intents into simulated orders, validates constraints before submission, simulates fills from normalized market data, tracks order lifecycle events, and maintains cash, positions, fees, realized PnL, and unrealized PnL.

This phase consumes the Phase 1 market universe and Phase 2 market-data substrate. It does not implement the full strategy research workbench, the operator console, live trading, wallet/auth flows, market/FOK/FAK strategy-layer orders, builder fees, or exchange-grade tick-by-tick queue reconstruction.

</domain>

<decisions>
## Implementation Decisions

### Phase 3 Minimum Scope
- **D-01:** P0 must include `OrderIntent`, limit and marketable-limit order handling, cancel and replace, an order state machine, depth-driven paper fills, partial fills, tick-size and minimum-size validation, submit/cancel latency, cash/position/fill/fee ledger entries, conservative mark valuation, realized/unrealized PnL, and basic hard risk controls.
- **D-02:** P1 follow-up work includes GTD expiry behavior, `post_only`, portfolio-level risk, reward estimate, and a more refined queue model.
- **D-03:** P2 deferred work includes pure market orders, FOK/FAK, builder fees, more complete OMS/EMS interfaces, and high-fidelity tick-by-tick replay-driven fills.

### Order Intent and Lifecycle
- **D-04:** Limit order is the standard order model exposed to strategies.
- **D-05:** Marketable limit orders are supported as limit orders that can cross the current book.
- **D-06:** Cancel and replace are in scope for P0 order lifecycle behavior.
- **D-07:** `client_order_id` is required as a first-class strategy-facing identifier for idempotency and traceability.
- **D-08:** GTC and GTD are the intended time-in-force semantics, but GTD expiry implementation is P1 rather than P0.
- **D-09:** `post_only` is an intended order flag, but its enforcement is P1 rather than P0.
- **D-10:** Pure market orders, FOK, and FAK should not be first-priority strategy-layer order types.

### Paper Fill Model
- **D-11:** P0 paper fills must account for orderbook depth, tick size, minimum order size, partial fills, submit latency, cancel latency, and conservative queue assumptions.
- **D-12:** The fill model should be conservative rather than optimistic when queue position or fill eligibility is uncertain.
- **D-13:** Complete tick-by-tick queue reconstruction, exchange-engine micro-priority replication, and exact user-stream event restoration are out of scope for P0.
- **D-14:** Fill simulation should consume Phase 2 normalized book snapshots, book levels, best bid/ask, and last trade rows before any future higher-fidelity replay feed is added.

### Ledger and PnL
- **D-15:** Ledger design must separate the factual layer from the valuation layer.
- **D-16:** The factual layer records submitted orders, state transitions, fills, cash movements, token position movements, and fees.
- **D-17:** The valuation layer computes marks, unrealized PnL, realized PnL, and exposure from factual ledger state plus current market data.
- **D-18:** Realized and unrealized PnL must be tracked separately.
- **D-19:** Default mark price uses a conservative valuation policy, not a best-case or mid-only assumption.
- **D-20:** Fees must be recorded in the core ledger.
- **D-21:** Rewards are tracked separately and must not be merged into core PnL.

### Risk Limits
- **D-22:** Balance, size, tick, single-order, single-market, and single-token position checks are hard rejects in P0.
- **D-23:** Portfolio exposure, event exposure, drawdown, and liquidity anomaly checks start as warnings/alerts, with the option to upgrade them to hard limits in later phases.
- **D-24:** Risk output must use a structured `RiskDecision` object so downstream services can record allow/deny/warn decisions consistently.
- **D-25:** Pre-trade risk checks must run before simulated order submission and before order state is advanced to an accepted/open state.

### the agent's Discretion
- Exact enum names and state-transition labels, as long as they distinguish intent, accepted/open, partially filled, filled, cancel requested, canceled, replace requested, rejected, and expired-capable states.
- Exact conservative mark policy, provided it is documented and avoids optimistic PnL.
- Exact latency configuration defaults, provided submit and cancel latency are both configurable.
- Exact schema layout for simulation tables, provided it keeps factual ledger rows separate from valuation snapshots.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition and project constraints
- `.planning/ROADMAP.md` — Phase 3 goal, requirements, and success criteria.
- `.planning/REQUIREMENTS.md` — SIM-01, SIM-02, SIM-03, and RISK-01 requirements.
- `.planning/PROJECT.md` — Project-level Python-first, simulation-first, event-driven, and live-trading-out-of-scope constraints.
- `.planning/STATE.md` — Current milestone status and known project risks.

### Prior phase substrate
- `.planning/phases/01-market-universe-metadata/01-CONTEXT.md` — Active + accepting universe boundary and source provenance expectations.
- `.planning/phases/01-market-universe-metadata/01-SPEC.md` — Locked market universe requirements and identifiers.
- `.planning/phases/02-historical-real-time-data-platform/02-CONTEXT.md` — Market-data scope, PostgreSQL layering, replay-fidelity boundary, and gap-fill/source markers.
- `.planning/phases/02-historical-real-time-data-platform/02-VERIFICATION.md` — Verified Phase 2 data capabilities and DATA-04 scope note.

### Existing implementation references
- `src/polymarket_quant/domain/market.py` — Canonical market identity and active/accepting market model.
- `src/polymarket_quant/domain/market_data.py` — `ReferenceToken`, `BookSnapshot`, `BookLevel`, `BestBidAsk`, `LastTrade`, and gap/source model.
- `src/polymarket_quant/storage/postgres_schema.sql` — Current PostgreSQL `reference`, `raw`, `normalized`, and `views` schema pattern.
- `src/polymarket_quant/storage/market_data_store.py` — Store/query pattern for PostgreSQL-backed market data.
- `src/polymarket_quant/services/market_data_queries.py` — Query service pattern for latest market state and price series.

### Research context
- `.planning/research/ARCHITECTURE.md` — Simulation Exchange and Risk Engine component boundaries and data-flow placement.
- `.planning/research/PITFALLS.md` — Phase 3 warnings for tick size, minimum size, partial fills, fees, rewards, and active/accepting status.
- `.planning/research/STACK.md` — Python-first, PostgreSQL, Pydantic, and event-driven stack direction.
- `.planning/research/SUMMARY.md` — Feasibility and build-order context.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ReferenceToken` carries `token_id`, `condition_id`, `outcome`, `liquidity`, `active`, `accepting_orders`, and universe ranking; simulation should use it for order validation and position identity.
- `BookSnapshot` and `BookLevel` provide depth data for P0 paper fill simulation.
- `BestBidAsk` provides current quote, spread, and midpoint values for conservative mark and marketable-limit checks.
- `LastTrade` can supplement valuation or diagnostics, but should not replace book-based fill logic.
- `MarketDataStore.fetch_latest_state()` and `fetch_price_series()` show the existing query-service style and PostgreSQL connection pattern.

### Established Patterns
- Domain models use Pydantic v2 with `extra="forbid"` and explicit validators for identifiers.
- Services are injectable and unit-testable with fake clients/stores rather than live API calls.
- PostgreSQL schema is currently layered into `reference`, `raw`, `normalized`, and `views`; Phase 3 should extend this pattern with simulation/ledger tables instead of mixing execution state into market-data tables.
- Existing UI work is Streamlit and table-first, but Phase 3 is primarily backend/service-layer work.

### Integration Points
- Order validation should join `OrderIntent` against reference token metadata and latest normalized market state.
- Fill simulation should consume Phase 2 book snapshots/book levels, BBO, and configurable latency.
- Ledger updates should be emitted from simulated order/fill events and persisted as immutable factual rows.
- Valuation views or services should read factual ledger state plus latest market data to compute conservative marks and PnL.
- Risk checks should run before simulated order acceptance and produce structured `RiskDecision` rows/events.

</code_context>

<specifics>
## Specific Ideas

- Limit order is the canonical strategy-facing order model.
- Marketable limit is supported because it preserves limit-price semantics while allowing immediate crossing.
- `client_order_id` is required for traceability and idempotency.
- Conservative queue behavior matters more than optimistic fill rates in the first paper exchange.
- Ledger must separate facts from valuations so later replay or valuation policy changes can recompute PnL without rewriting fill history.
- Rewards are a separate attribution stream and should not inflate core PnL.
- Risk checks should have consistent structured outputs, not scattered booleans or ad hoc error strings.

</specifics>

<deferred>
## Deferred Ideas

- P1: GTD expiry implementation.
- P1: `post_only` enforcement.
- P1: Portfolio-level risk hardening.
- P1: Reward estimate.
- P1: More refined queue model.
- P2: Pure market order, FOK, and FAK strategy-layer order types.
- P2: Builder fees.
- P2: More complete OMS/EMS interface.
- P2: High-fidelity tick-by-tick replay-driven fills.

</deferred>

---
*Phase: 03-simulation-exchange-portfolio-ledger*
*Context gathered: 2026-04-19*
