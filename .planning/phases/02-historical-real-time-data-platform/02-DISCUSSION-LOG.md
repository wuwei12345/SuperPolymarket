# Phase 2: Historical & Real-Time Data Platform - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-18T09:13:27Z
**Phase:** 02-historical-real-time-data-platform
**Areas discussed:** Data scope and priority, REST backfill strategy, realtime WebSocket collection, storage and replay shape, minimum delivery

---

## Data Scope and Priority

| Option | Description | Selected |
|--------|-------------|----------|
| Price history + snapshots + BBO/last trade | Capture `price_history`, `orderbook_snapshot`, `best_bid_ask`, and `last_trade`; derive spread/midpoint. | yes |
| Full public data upfront | Add Data API trades/activity as mandatory ingestion before Phase 2 can pass. | |
| Realtime only first | Skip REST backfill and build only WS collector. | |

**User's choice:** First collect `price_history`, `orderbook_snapshot`, `best_bid_ask`, and `last_trade`; derive `spread` / `midpoint`; do not make trades/activity a hard upfront dependency.

---

## REST Backfill Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Automated prioritized universe backfill | Pick top N tokens from active/accepting universe; backfill price history and immediately fetch a current book snapshot. | yes |
| Manual token-driven backfill | User manually selects token IDs each run. | |
| Snapshot-only backfill | Avoid price history and capture only current state. | |

**User's choice:** Start with REST batch backfill. For each token, run price history backfill, then immediately fetch a current snapshot. Universe should auto-batch with priority instead of being manually driven.

---

## Realtime WebSocket Collection

| Option | Description | Selected |
|--------|-------------|----------|
| Token-based market channel collector | Subscribe by `token_id`; capture book, price changes, BBO, last trade, and tick-size changes. | yes |
| Minimal ticker-only collector | Only capture latest price/BBO style updates. | |
| Full private/user stream | Include authenticated user channel/order events. | |

**User's choice:** Subscribe to `book`, `price_change`, `best_bid_ask`, `last_trade_price`, and `tick_size_change`, keyed by `token_id`.

**Notes:** User wants hot/warm/cold token pools: hot resident, warm rotating, cold low frequency. Disconnect recovery should use REST snapshot plus recent price history, and raw events must be persisted exactly.

---

## Storage and Replay Shape

| Option | Description | Selected |
|--------|-------------|----------|
| PostgreSQL layered storage | Use `reference -> raw -> normalized -> views` layers. | yes |
| Continue SQLite only | Extend Phase 1 SQLite approach for Phase 2. | |
| Full exchange-grade replay | Attempt lossless orderbook reconstruction immediately. | |

**User's choice:** Switch to PostgreSQL. Use strict layers: `reference`, `raw`, `normalized`, `views`.

**Notes:** Replay should be research-grade first, not exchange-grade lossless reconstruction. Source/gap markers are required.

---

## Minimum Delivery

| Deliverable | Selected |
|-------------|----------|
| Universe automatically selects top N active/accepting tokens | yes |
| Historical price backfill for top N | yes |
| Current book snapshot for top N | yes |
| WS realtime subscription for top N | yes |
| Disconnect/reconnect gap fill | yes |
| Raw and normalized database layers | yes |
| Page shows latest bid/ask, spread, last trade, recent price curve, source, gap markers | yes |

**User's choice:** All listed items are part of Phase 2 minimum delivery.

---

## the agent's Discretion

- Exact default top N value and priority formula.
- PostgreSQL migration tooling and exact schema/index layout.
- Hot/warm/cold pool sizing and rotation intervals.
- Inspection page layout details.

## Deferred Ideas

- Full trades/activity ingestion.
- Exchange-grade no-loss replay.
- Strategy, execution, portfolio, PnL, and risk UI.
