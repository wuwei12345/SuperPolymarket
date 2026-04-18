# Features Research

**Verified against official Polymarket docs:** 2026-04-18

## Table Stakes

These are baseline capabilities a usable Polymarket quant simulator should have.

### Market Universe

- Sync active markets and events from Gamma
- Track `conditionId`, Yes/No `tokenId`s, category, end date, volume, liquidity
- Filter out closed, archived, restricted, or non-accepting markets

### Market Data

- Fetch public orderbook, price, midpoint, spread, and price history from CLOB
- Subscribe to market WebSocket for near real-time book and trade events
- Persist historical snapshots for replay and debugging

### Simulation & Ledger

- Express orders in the same shape Polymarket expects: side, price, size, order type
- Model partial fills, cancellations, and position updates
- Track PnL, inventory, and exposure per strategy and market

### Research Workflow

- Run the same strategy logic in backtest and live-paper modes
- Compare strategy outputs across multiple market universes
- Save experiment parameters and outputs for reproducibility

## Differentiators

These are higher-leverage features that can create edge after the base system works.

- Binary-market-specific signal library: midpoint skew, spread compression, event proximity, market resolution timing
- Liquidity-aware sizing and queue-position-aware execution heuristics
- Reward and rebate aware market selection on fee-enabled/reward-enabled markets
- Cross-market event clustering and conflict detection (shared event/topic exposure)
- Shadow live mode: compare simulated fills against actual visible market evolution without sending orders

## Anti-Features

These should stay out of v1 unless new evidence changes priorities.

| Feature | Why Not In v1 |
|---------|---------------|
| Real-money execution automation | Compliance, key management, and operational blast radius are too high before simulator fidelity is proven |
| Cross-exchange routing | Weakens focus on Polymarket-specific edge and adds schema complexity |
| Generic retail portfolio app | Not aligned with the user's self-directed quant workflow |
| HFT-style quoting across thousands of markets | Premature optimization before data and simulation fidelity exist |

## Key Implications For Requirements

- The system must be event-driven, not cron-only.
- The first milestone should prioritize normalized market metadata plus replayable market data.
- Execution realism must include tick size, min size, depth, and latency, or performance metrics will be misleading.

## Sources

- [Introduction](https://docs.polymarket.com/api-reference/introduction)
- [Quickstart](https://docs.polymarket.com/quickstart)
- [Orderbook](https://docs.polymarket.com/trading/orderbook)
- [WebSocket Overview](https://docs.polymarket.com/market-data/websocket/overview)
- [Maker Rebates](https://docs.polymarket.com/market-makers/maker-rebates)
