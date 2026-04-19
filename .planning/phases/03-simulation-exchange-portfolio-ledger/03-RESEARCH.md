---
phase: 03-simulation-exchange-portfolio-ledger
status: complete
researched_at: 2026-04-19
sources_checked: official_polymarket_docs, local_codebase, planning_artifacts
---

# Phase 3 Research: Simulation Exchange & Portfolio Ledger

## Research Goal

Answer what the planner needs to know to build Phase 3 well: a simulation-first Polymarket paper exchange with order intent, order lifecycle, depth-driven fills, factual ledger, conservative valuation, PnL, and structured risk decisions.

## Source-Backed Facts

### Polymarket order semantics

- Official order lifecycle docs state that Polymarket orders are limit orders.
- "Market orders" are represented as marketable limit orders that execute immediately against resting orders.
- Marketable logic is side-dependent: buy price crosses when it is greater than or equal to the lowest ask; sell price crosses when it is less than or equal to the highest bid.
- Orders can rest until matched, canceled, or expired for GTD orders.
- Official validation includes sufficient balance/allowance and minimum tick-size compliance.
- Official error codes cover post-only crossing, tick-size violations, minimum-size violations, duplicate orders, crossing-book errors, insufficient balance/allowance, invalid expiration, and delayed matching.

### Market data available for simulation

- CLOB order book responses include `market` condition ID, `asset_id` token ID, sorted `bids`, sorted `asks`, `min_order_size`, `tick_size`, `neg_risk`, and `last_trade_price`.
- Phase 2 already normalizes `BookSnapshot`, `BookLevel`, `BestBidAsk`, and `LastTrade` records and stores source/gap markers.
- Phase 2 replay is research-grade, not exchange-grade lossless reconstruction. Phase 3 must not claim exact queue position or exchange matching priority.

### Fees and rewards

- Current official docs describe taker fees using `fee = C * feeRate * p * (1 - p)`.
- Makers are not charged fees in the official fee model, while takers pay fees.
- Fees are applied at match time and rounded to 5 decimal places, with very small fees potentially rounding to zero.
- Rewards/rebates are separate maker incentive programs, not core trade PnL. User explicitly decided rewards should be tracked separately and not merged into core PnL.

## Implementation Guidance

### Model boundaries

Use a dedicated simulation domain module rather than adding execution fields to `market_data.py`.

Recommended domain symbols:

- `OrderSide`: `BUY`, `SELL`
- `OrderType`: `LIMIT`
- `TimeInForce`: `GTC`, `GTD`
- `OrderStatus`: `PENDING`, `ACCEPTED`, `OPEN`, `PARTIALLY_FILLED`, `FILLED`, `CANCEL_REQUESTED`, `CANCELED`, `REPLACE_REQUESTED`, `REPLACED`, `REJECTED`, `EXPIRED`
- `RiskDecisionType`: `ALLOW`, `WARN`, `REJECT`
- `OrderIntent`
- `SimulatedOrder`
- `OrderStateTransition`
- `SimulatedFill`
- `CashLedgerEntry`
- `PositionLedgerEntry`
- `PositionState`
- `ValuationSnapshot`
- `RiskDecision`
- `SimulationConfig`

Keep pure validation helpers in domain/services so tests can run without PostgreSQL.

### Storage boundary

Extend the existing PostgreSQL layering without mixing execution state into market-data tables.

Recommended schemas/tables:

- `simulation.orders`
- `simulation.order_transitions`
- `simulation.fills`
- `simulation.cash_ledger`
- `simulation.position_ledger`
- `simulation.risk_decisions`
- `simulation.valuation_snapshots`

Add `views.simulation_positions` and `views.simulation_pnl` as query-friendly views.

Use immutable event/fact rows for fills, cash entries, position entries, and state transitions. Upsert only current order state where necessary; preserve transition history.

### Risk checks

P0 hard rejects:

- blank or duplicate `client_order_id`
- unsupported order type
- unsupported side
- price outside `[0.00, 1.00]`
- price not aligned with `tick_size`
- size below `min_order_size`
- insufficient cash for buy orders including estimated fee
- insufficient token position for sell orders
- single-order notional exceeds configured max
- single-token or single-market position would exceed configured max

P0 warnings:

- portfolio exposure threshold
- event exposure threshold
- drawdown threshold
- liquidity anomaly threshold

All checks should produce `RiskDecision` objects with:

- `decision`: `ALLOW`, `WARN`, or `REJECT`
- `checks`: list of structured check results
- `reasons`: list of machine-readable reason codes
- `warnings`: list of warning reason codes
- `client_order_id`
- `token_id`
- `condition_id`

### Fill model

P0 fill engine should:

- consume `BookSnapshot` or explicit `BookLevel` lists
- apply submit latency before deciding whether an order is eligible to interact with a book snapshot
- apply cancel latency before cancel state takes effect
- use asks to fill buys and bids to fill sells
- match only levels that satisfy the limit price
- consume depth level by level
- produce partial fills when available depth is smaller than remaining size
- leave residual quantity open for GTC orders
- use conservative queue assumptions for resting liquidity, such as requiring a later contra-side book move/trade before filling newly rested orders

Avoid:

- pretending exact queue priority is known
- using `last_trade_price` alone as fill proof
- treating gap-filled data as equally reliable for high-fidelity fills without a marker

### Ledger and valuation

Factual layer:

- order accepted/rejected/canceled/replaced events
- fills with price, size, side, liquidity role, fee, source snapshot ID/time
- cash debits/credits
- position quantity changes
- fee entries

Valuation layer:

- conservative mark price per token
- position notional
- realized PnL
- unrealized PnL
- total equity
- exposure by token/market/event where available

Conservative mark policy should avoid optimistic marks:

- Long Yes/No token: prefer best bid when available; otherwise use last trade or zero fallback with explicit reason.
- Short or sell-side exposure: prefer best ask when applicable.
- Never use midpoint as the default conservative mark unless both sides exist and the policy explicitly labels it less conservative.

## Validation Architecture

Phase 3 can be validated with deterministic unit tests and fake stores. No live Polymarket API or live PostgreSQL is required for P0 tests.

Required automated checks:

- `pytest tests/unit/test_simulation_models.py -q`
- `pytest tests/unit/test_simulation_store.py -q`
- `pytest tests/unit/test_order_risk.py -q`
- `pytest tests/unit/test_fill_engine.py -q`
- `pytest tests/unit/test_portfolio_ledger.py -q`
- `pytest tests/unit/test_paper_exchange.py -q`
- `pytest -q`

Required grep checks:

- `rg "class OrderIntent|class RiskDecision|class SimulatedFill" src/polymarket_quant/domain/simulation.py`
- `rg "CREATE SCHEMA IF NOT EXISTS simulation|simulation.orders|simulation.fills|simulation.risk_decisions" src/polymarket_quant/storage/postgres_schema.sql`
- `rg "def validate_order_intent|def apply_risk_checks" src/polymarket_quant/services/order_risk.py`
- `rg "def simulate_fills|partial" src/polymarket_quant/services/fill_engine.py`
- `rg "realized_pnl|unrealized_pnl|conservative" src/polymarket_quant/services/portfolio_ledger.py`

## Planning Implications

- Put domain models and schema/store first.
- Build risk and order lifecycle before paper exchange orchestration so order submission has a structured decision surface.
- Build fill engine separately so it can be tested with deterministic book snapshots.
- Build ledger/valuation after fills so accounting can consume fill facts.
- Add a final orchestration plan that wires risk, state machine, fill engine, ledger, valuation, README docs, and end-to-end tests.

## External Sources

- https://docs.polymarket.com/concepts/order-lifecycle
- https://docs.polymarket.com/api-reference/market-data/get-order-book
- https://docs.polymarket.com/resources/error-codes
- https://docs.polymarket.com/trading/fees
- https://docs.polymarket.com/market-makers/liquidity-rewards

## RESEARCH COMPLETE
