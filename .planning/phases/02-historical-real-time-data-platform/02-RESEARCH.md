# Phase 02 — Research: Historical & Real-Time Data Platform

**Created:** 2026-04-18
**Status:** Research complete

## Research Question

What do we need to know to plan Phase 2 well: selecting a top-N active/accepting token universe, backfilling CLOB price history and current book snapshots, collecting market WebSocket events, marking reconnect gap fills, and storing raw plus normalized data in PostgreSQL?

## Source Findings

### Polymarket API surfaces

- Official docs split public market data across Gamma, Data, and CLOB APIs. Gamma is market discovery, Data is positions/trades/activity/analytics, and CLOB is orderbook, pricing, midpoint, spread, and price history.
- Public market data REST endpoints do not require an API key, wallet, or authentication. Phase 2 can stay simulation-first and unauthenticated.
- CLOB `/prices-history` retrieves historical price data. Its query parameter is named `market`, but official orderbook docs note it takes a token ID / asset ID.
- CLOB `/batch-prices-history` supports multiple market asset IDs in one request, with a maximum of 20 IDs per request body.
- CLOB `/books` supports batch orderbook snapshots for token IDs and returns `market`, `asset_id`, `timestamp`, `hash`, `bids`, `asks`, `min_order_size`, `tick_size`, `neg_risk`, and `last_trade_price`.
- CLOB `/prices` can fetch best BUY/SELL prices for token IDs. For our normalized view, BUY maps to best bid and SELL maps to best ask.
- CLOB `/last-trades-prices` supports up to 500 token IDs per request and returns last trade price plus side.

### WebSocket market channel

- Market channel endpoint: `wss://ws-subscriptions-clob.polymarket.com/ws/market`.
- Subscription payload uses `assets_ids` with token IDs and `type: "market"`.
- `custom_feature_enabled: true` is required to receive `best_bid_ask` events.
- Relevant event types for Phase 2:
  - `book`: initial/full orderbook snapshot and later book-affecting updates
  - `price_change`: price level updates; `size: "0"` means a level is removed
  - `tick_size_change`: minimum tick changes near book price limits
  - `last_trade_price`: trade executions with price, side, size, timestamp
  - `best_bid_ask`: best prices plus spread, gated behind `custom_feature_enabled`
- Raw WebSocket events should be persisted before any normalization because the docs changed `price_change` shape in September 2025 and CLOB V2 changes are scheduled around April 22, 2026. Raw retention protects replay research against schema drift.

### Rate limits and batching

- Official rate limits are high but finite. Relevant published limits include CLOB `/books` at 500 requests per 10 seconds, `/prices` at 500 requests per 10 seconds, `/prices-history` at 1000 requests per 10 seconds, Data API general at 1000 requests per 10 seconds, and Data `/trades` at 200 requests per 10 seconds.
- Phase 2 should use batch endpoints where available and add local chunk sizes that stay below documented maximums:
  - price history chunk size: 20 token IDs
  - book snapshot chunk size: 100 token IDs by default
  - last trade chunk size: 500 token IDs maximum, lower default acceptable
- Use bounded retries and timeline events rather than unbounded retry loops. Cloudflare throttling may delay requests instead of immediately rejecting them.

### PostgreSQL storage model

- User locked the storage boundary as `reference -> raw -> normalized -> views`.
- PostgreSQL should be introduced as the Phase 2 operational store while Phase 1 SQLite remains usable for the market universe UI.
- Use explicit SQL schema files and a small `psycopg` repository layer rather than adding a heavy ORM. This matches the current lightweight codebase and keeps DDL visible for review.
- Use JSONB for raw REST and WebSocket payloads, typed columns for query keys, and generated/query views for latest state.
- Store all relevant timestamps with timezone semantics:
  - `received_at`: local ingestion timestamp
  - `source_ts`: event/snapshot timestamp supplied by Polymarket when available
  - `gap_fill`: boolean marker for records created during disconnect repair
  - `collection_run_id` / `connection_id`: traceability keys for backfill and WS sessions

### Normalization and replay fidelity

- Phase 2 should not pretend to produce exchange-grade lossless replay. Research-grade replay is acceptable if gaps, snapshots, and source payloads are visible.
- Persist raw REST payloads and raw WS events first, then derive normalized records:
  - price history points
  - orderbook snapshot headers and levels
  - best bid/ask rows with derived spread and midpoint
  - last trade rows
  - gap fill intervals
- Query views should expose latest bid/ask, spread, midpoint, last trade, price series, source labels, and gap markers for strategy and UI consumers.
- Reconnect handling should create a gap interval and fill it with one REST `/books` snapshot plus recent `/prices-history` points. Those records must carry `gap_fill = true`.

## Recommended Technical Approach

### App shape

Use the existing Python package and add these modules:

- `src/polymarket_quant/domain/market_data.py` — Pydantic/dataclass models for token universe, price points, book snapshots, BBO, last trade, gap intervals, and raw event envelopes.
- `src/polymarket_quant/storage/postgres_schema.sql` — PostgreSQL schemas, tables, indexes, and views.
- `src/polymarket_quant/storage/market_data_store.py` — `psycopg` repository for schema init and raw/normalized upserts.
- `src/polymarket_quant/services/universe_selector.py` — top-N token selection from Phase 1 `MarketStore`.
- `src/polymarket_quant/services/backfill.py` — REST batch backfill orchestration.
- `src/polymarket_quant/adapters/polymarket.py` — extend existing `ClobClient` with price history, batch books, prices, and last trade methods.
- `src/polymarket_quant/adapters/polymarket_ws.py` — async market WebSocket client with injectable connector for tests.
- `src/polymarket_quant/services/realtime_collector.py` — subscription scheduling, raw event persistence, normalization, and reconnect gap fill.
- `src/polymarket_quant/services/market_data_queries.py` — query DTOs/dataframes for the inspection page and future strategies.
- `src/polymarket_quant/ui/market_data_app.py` — Streamlit inspection page.

### Defaults

- `DATABASE_URL` is the Phase 2 PostgreSQL DSN env var.
- `POLYMARKET_TOP_N` default is `50` tokens.
- Ranking formula: liquidity descending, then earlier non-expired `end_date`, then question. Each Phase 1 market contributes Yes and No token rows.
- REST backfill default interval: `1d`; fidelity: `1` minute; recent gap-fill interval: last 60 minutes.
- Hot/warm/cold defaults:
  - hot pool: top 50 tokens, resident
  - warm pool: next 100 tokens, rotate every 10 minutes
  - cold pool: remaining selected tokens, sample every 60 minutes
- Test code should keep these values configurable and use small fake fixtures.

### Validation Architecture

Phase 2 should be validated mostly with deterministic unit tests:

- SQL schema text tests verify required schemas/tables/views/indexes exist.
- Repository tests use fake cursors or a DSN-gated integration test; CI-style unit tests must not require a running PostgreSQL server.
- REST adapter tests use `httpx.MockTransport` and verify exact endpoints, chunking, raw payload preservation, and normalized rows.
- WebSocket tests use fake async message iterators and fake stores to verify subscription payload, event persistence before normalization, reconnect events, and gap-fill service calls.
- UI contract tests verify required columns/copy/transforms without launching a browser.
- A manual live smoke can be documented for a local PostgreSQL DSN and real public Polymarket endpoints.

## Risks and Guardrails

- **CLOB V2 drift risk:** Official changelog includes CLOB V2 downtime/upgrade notes around April 22, 2026. Keep raw payloads, tolerate unknown JSON fields, and centralize endpoint constants.
- **ID mismatch risk:** All realtime and backfill keys use token IDs. Store `condition_id` as a join key but do not subscribe by condition ID on the market channel.
- **Data loss risk:** Raw WS event insert must happen before normalized derivation. Normalization failures should create error timeline rows, not drop raw events.
- **Overstated replay risk:** Views and UI must show `gap_fill` and `source` markers so repaired intervals are distinguishable from live data.
- **Operational dependency risk:** PostgreSQL may not be installed locally. Plans must include `user_setup` and env-gated tests rather than silently falling back to SQLite for Phase 2 data.
- **Scope creep risk:** Do not build strategy logic, simulated fills, portfolio/PnL, authenticated user channel, live trading, or full Data API trades/activity ingestion in this phase.

## Sources

- [Polymarket API Introduction](https://docs.polymarket.com/api-reference/introduction)
- [Market Data Overview](https://docs.polymarket.com/market-data/overview)
- [Get prices history](https://docs.polymarket.com/api-reference/markets/get-prices-history)
- [Get batch prices history](https://docs.polymarket.com/api-reference/markets/get-batch-prices-history)
- [Orderbook guide](https://docs.polymarket.com/trading/orderbook)
- [Get order books](https://docs.polymarket.com/api-reference/market-data/get-order-books-request-body)
- [Get market prices](https://docs.polymarket.com/api-reference/market-data/get-market-prices-request-body)
- [Get last trade prices](https://docs.polymarket.com/api-reference/market-data/get-last-trade-prices-request-body)
- [Market WebSocket channel](https://docs.polymarket.com/market-data/websocket/market-channel)
- [Rate Limits](https://docs.polymarket.com/api-reference/rate-limits)
- [Polymarket Changelog](https://docs.polymarket.com/changelog)

## RESEARCH COMPLETE
