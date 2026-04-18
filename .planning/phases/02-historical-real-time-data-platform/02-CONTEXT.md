# Phase 2: Historical & Real-Time Data Platform - Context

**Gathered:** 2026-04-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 2 delivers the public market-data substrate for the simulator: REST historical backfill, current orderbook snapshots, WebSocket market-event capture, reconnect gap filling, and research-grade replay/query views. It consumes the Phase 1 market universe and produces durable raw and normalized data that later strategy, replay, and paper-execution phases can use.

This phase does not implement strategy logic, simulated fills, portfolio/PnL accounting, live trading, wallet/auth flows, or user-channel private order updates.

</domain>

<decisions>
## Implementation Decisions

### Data scope and priority
- **D-01:** Phase 2 first-class collected data is `price_history`, `orderbook_snapshot`, `best_bid_ask`, and `last_trade`.
- **D-02:** `spread` and `midpoint` are derived normalized fields, not independently collected source payloads.
- **D-03:** Data API `trades` and `activity` are not hard prerequisites for Phase 2 minimum delivery. They can be added later for calibration/analysis, but planning should not block on full trades/activity ingestion.

### REST backfill strategy
- **D-04:** Start with REST batch backfill before relying on realtime streams.
- **D-05:** For each selected token, run historical price backfill and then immediately fetch a current orderbook snapshot.
- **D-06:** Backfill should run automatically over a prioritized market/token universe, not primarily as a manual token picker.
- **D-07:** The token universe comes from Phase 1 active + accepting markets and is ranked into a top N working set.

### Real-time WebSocket collection
- **D-08:** Subscribe to market-channel events for `book`, `price_change`, `best_bid_ask`, `last_trade_price`, and `tick_size_change`.
- **D-09:** `token_id` is the primary subscription and data key for realtime market data.
- **D-10:** Subscription scheduling uses three pools: hot pool is always subscribed, warm pool rotates, and cold pool is sampled at lower frequency.
- **D-11:** On disconnect/reconnect, fill gaps with REST orderbook snapshot plus recent price history. The repaired interval must be marked as gap-filled instead of pretending it is uninterrupted live data.
- **D-12:** Raw WebSocket events must be persisted exactly as received before normalization.

### Storage model
- **D-13:** Phase 2 should move from SQLite to PostgreSQL.
- **D-14:** Storage must be layered: `reference` -> `raw` -> `normalized` -> `views`.
- **D-15:** `reference` stores market/token metadata and universe membership imported from Phase 1.
- **D-16:** `raw` stores original REST responses and WebSocket event payloads with source, received time, token/condition identifiers, and gap/reconnect context.
- **D-17:** `normalized` stores queryable price history, book snapshots, best bid/ask, last trade, and derived spread/midpoint fields.
- **D-18:** `views` expose research/operator-friendly latest state and time-window queries.

### Replay fidelity boundary
- **D-19:** Replay for Phase 2 targets "research-grade" reconstruction, not exchange-grade lossless orderbook replay.
- **D-20:** Research-grade replay should support strategy research, debugging, and time-window analysis while explicitly marking gaps, snapshots, and derived fields.
- **D-21:** Exchange-grade no-loss replay and full depth event-perfect reconstruction are deferred unless a later phase or validation gap demands it.

### Phase 2 minimum delivery
- **D-22:** Automatically select top N active/accepting tokens from the Phase 1 universe.
- **D-23:** Backfill historical price data for top N tokens.
- **D-24:** Fetch current book snapshots for top N tokens after each token's backfill.
- **D-25:** Realtime WebSocket subscriptions run for top N tokens.
- **D-26:** Disconnect/reconnect can fill gaps using REST snapshot plus recent price history.
- **D-27:** Data lands in separate raw and normalized layers.
- **D-28:** A page or inspectable UI surface must show latest bid/ask, spread, last trade, recent price curve, data source, and gap-fill markers.

### the agent's Discretion
- Exact top N default value and ranking formula, as long as it prioritizes active/accepting markets using available liquidity/activity/freshness signals.
- Exact PostgreSQL schema names, indexes, and migration tooling after research validates the best local pattern.
- Exact hot/warm/cold pool sizes and rotation intervals, as long as they are configurable.
- Exact chart/table presentation for the Phase 2 inspection page, as long as the required fields and gap/source markers are visible.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition and project constraints
- `.planning/ROADMAP.md` — Phase 2 goal, requirements, and success criteria.
- `.planning/REQUIREMENTS.md` — DATA-01, DATA-02, DATA-03, DATA-04 requirements.
- `.planning/PROJECT.md` — Project-level Python-first, simulation-first, event-driven, and historical-fidelity constraints.
- `.planning/STATE.md` — Current milestone status and known risks.

### Prior phase substrate
- `.planning/phases/01-market-universe-metadata/01-CONTEXT.md` — Phase 1 decisions and market universe boundary.
- `.planning/phases/01-market-universe-metadata/01-VERIFICATION.md` — Verified Phase 1 capabilities and scope note.
- `.planning/phases/01-market-universe-metadata/01-UAT.md` — User UAT results, including resolved sync gap and source provenance expectations.
- `src/polymarket_quant/domain/market.py` — Canonical market and source provenance models.
- `src/polymarket_quant/storage/market_store.py` — Phase 1 local market universe persistence.
- `src/polymarket_quant/adapters/polymarket.py` — Existing Gamma/CLOB client style.

### Research context
- `.planning/research/ARCHITECTURE.md` — Recommended data-flow boundaries and entity model.
- `.planning/research/PITFALLS.md` — Phase 2 pitfalls around REST-only realtime, replay fidelity, and ID mapping.
- `.planning/research/SUMMARY.md` — Feasibility and build-order summary.
- `.planning/research/STACK.md` — Python-first stack direction.

### External docs to verify during research
- Official Polymarket CLOB REST docs for price history, orderbook, and best bid/ask endpoints.
- Official Polymarket Market WebSocket docs for `book`, `price_change`, `best_bid_ask`, `last_trade_price`, and `tick_size_change` payloads.
- Official Polymarket Data API docs for future `trades`/`activity` calibration work, explicitly non-blocking for minimum Phase 2.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CanonicalMarket` and `MarketSourceMap` provide the market/token identity model that Phase 2 should reference instead of inventing new identifiers.
- `MarketStore.list_markets()` provides the current active + accepting market universe; Phase 2 may import this into PostgreSQL `reference` tables.
- `GammaClient` and `ClobClient` establish simple injectable `httpx.Client` adapter patterns for testable REST clients.
- `MarketSyncService` and `SyncEvent` establish the timeline/status event style that the Phase 2 inspection page can reuse or mirror.

### Established Patterns
- Python package uses `src/` layout with pytest configured in `pyproject.toml`.
- Tests use deterministic fake clients / `httpx.MockTransport`, avoiding live API dependency in CI-style unit tests.
- Phase 1 UI is Streamlit-style and table-first; Phase 2 can add an inspection page if useful, but should avoid becoming the full operator console.
- Source provenance matters: raw/normalized/view layers must carry source and gap markers forward.

### Integration Points
- Phase 2 should read the Phase 1 universe and convert top N market/token rows into PostgreSQL `reference` records.
- Backfill and WebSocket collectors should write raw payloads before normalization.
- Normalized latest-state views should feed the Phase 2 inspection page and later strategy/replay phases.

</code_context>

<specifics>
## Specific Ideas

- User wants top N tokens selected automatically from active + accepting markets, with priority ranking rather than manual selection as the main workflow.
- User wants hot/warm/cold token pools for realtime subscriptions: hot is resident, warm rotates, cold is low-frequency.
- User explicitly wants gap-fill markers visible; repaired data should not be indistinguishable from uninterrupted live data.
- User wants a page to inspect latest bid/ask, spread, last trade, recent price curve, data source, and gap-fill markers.

</specifics>

<deferred>
## Deferred Ideas

- Full trades/activity ingestion from Data API is deferred; it should not block Phase 2 minimum delivery.
- Exchange-grade lossless replay is deferred. Phase 2 targets research-grade replay with explicit gap/source markers.
- Strategy execution, simulated fills, positions, PnL, and risk controls remain Phase 3+.

</deferred>

---
*Phase: 02-historical-real-time-data-platform*
*Context gathered: 2026-04-18*
