# Architecture Research

**Verified against official Polymarket docs:** 2026-04-18

## Recommended Component Boundaries

| Component | Responsibility | Key Inputs | Key Outputs |
|-----------|----------------|-----------|-------------|
| Market Registry | Normalize Gamma/CLOB market metadata into a canonical universe | Gamma markets/events, CLOB simplified markets | Canonical market/event/token tables |
| Historical Loader | Pull REST snapshots and price history in batches | Gamma/Data/CLOB REST | Backfill tables and raw snapshot archive |
| Real-Time Collector | Capture WebSocket market events and optional user events | Market WS, later User WS | Replayable event log, latest book state |
| Feature Pipeline | Transform normalized events into strategy-ready features | Canonical market data | Feature tables, signals, derived metrics |
| Strategy Runtime | Run research, backtest, and live-paper strategies | Feature streams, configs, market universe | Order intents, analytics, experiment outputs |
| Simulation Exchange | Convert intents into paper orders/fills using Polymarket semantics | Order intents, book state, constraints | Orders, fills, positions, cash movements |
| Risk Engine | Apply pre-trade and post-trade checks | Orders, fills, exposures, market state | Allow/deny decisions, alerts |
| Operator Console | Visualize health, orders, PnL, and experiment status | Query API / analytics tables | Dashboard, alerts, operator actions |

## Data Flow

1. Gamma + CLOB simplified markets build the canonical market registry.
2. Historical loaders backfill metadata, prices, trades, and other public data into durable storage.
3. Real-time collectors subscribe to market WebSocket streams and append immutable events.
4. Normalizers transform raw events into current book state, trade tape, and feature inputs.
5. Strategy runtime emits order intents against the same canonical schema in backtest or live-paper mode.
6. Simulation exchange consumes order intents and the latest book state to create fills and position updates.
7. Risk engine evaluates exposures and can block new intents or freeze markets.
8. Operator console reads from the query layer and exposes observability to the user.

## Important Entity Model

- `event`: the umbrella real-world event or topic
- `market`: a single question/contract within that event
- `condition_id`: the tradeable market identifier used in several CLOB/user contexts
- `token_id`: the specific Yes/No asset IDs used for market data subscriptions and orders

This distinction must be explicit in code. The WebSocket market channel subscribes by `asset_id` (`token_id`), while the user channel subscribes by `markets` (`condition_id`).

## Suggested Build Order

1. Canonical market registry
2. Historical + real-time market data ingestion
3. Replayable event log and normalized state views
4. Simulation exchange and portfolio ledger
5. Strategy framework and experiment tracking
6. Operator dashboard and safety controls
7. Optional live bridge after simulator fidelity is validated

## Sources

- [Introduction](https://docs.polymarket.com/api-reference/introduction)
- [Get Simplified Markets](https://docs.polymarket.com/api-reference/markets/get-simplified-markets)
- [WebSocket Overview](https://docs.polymarket.com/market-data/websocket/overview)
- [Get Current Positions For A User](https://docs.polymarket.com/api-reference/core/get-current-positions-for-a-user)
