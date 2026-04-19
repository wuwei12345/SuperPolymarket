# Phase 3: Simulation Exchange & Portfolio Ledger - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-19
**Phase:** 03-simulation-exchange-portfolio-ledger
**Areas discussed:** Order Intent and Lifecycle, Paper Fill Model, Ledger and PnL, Risk Limits, Phase 3 Minimum Scope

---

## Order Intent and Lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Limit order as standard model | Strategy layer expresses orders as Polymarket-style limit intents | yes |
| Marketable limit | Limit orders may cross the current book and fill immediately where eligible | yes |
| Cancel / replace | Simulated order lifecycle supports cancellation and replacement | yes |
| client_order_id | Strategy-facing id for idempotency and traceability | yes |
| GTC / GTD | Support good-till-cancel and good-till-date semantics | partial |
| post_only | Support maker-only order behavior | partial |
| Pure market / FOK / FAK | Additional order types exposed directly to strategies | no |

**User's choice:** Limit order is the standard model. Support marketable limit, cancel/replace, `client_order_id`, GTC/GTD semantics, and `post_only`; do not prioritize pure market/FOK/FAK for the strategy layer.

**Notes:** GTD expiry and `post_only` were later classified as P1 rather than P0.

---

## Paper Fill Model

| Option | Description | Selected |
|--------|-------------|----------|
| Depth-driven fills | Use orderbook depth rather than top-of-book only | yes |
| Tick and minimum-size checks | Validate market constraints before acceptance/fill | yes |
| Partial fills | Orders can fill incrementally | yes |
| Submit/cancel latency | Simulate timing delay for order submission and cancellation | yes |
| Conservative queue rules | Avoid optimistic fill assumptions where queue position is unknown | yes |
| Complete queue reconstruction | Rebuild full exchange queue from tick-level events | no |
| Engine-level priority replica | Recreate microscopic CLOB matching priority | no |
| Exact user-stream restoration | Fully restore user event stream for fills | no |

**User's choice:** P0 fill model must include depth, tick size, minimum order size, partial fills, submit/cancel latency, and conservative queue assumptions.

**Notes:** Complete tick-by-tick queue reconstruction, exchange-engine micro-priority replication, and exact user-stream restoration are explicitly out of P0 scope.

---

## Ledger and PnL

| Option | Description | Selected |
|--------|-------------|----------|
| Factual layer | Immutable order, fill, cash, position, and fee facts | yes |
| Valuation layer | Derived marks, exposures, unrealized PnL, and realized PnL views/snapshots | yes |
| Separate realized/unrealized | Track realized and unrealized PnL independently | yes |
| Conservative mark | Default valuation should avoid optimistic marks | yes |
| Fee in core ledger | Fees must be recorded as core ledger facts | yes |
| Rewards in core PnL | Merge rewards into core PnL | no |

**User's choice:** Ledger is split into factual and valuation layers. Realized/unrealized PnL are separate. Default mark uses a conservative policy. Fees are mandatory ledger facts. Rewards are tracked separately and not merged into core PnL.

**Notes:** The fact/valuation split is important so later valuation-policy changes can recompute marks without mutating historical fills.

---

## Risk Limits

| Option | Description | Selected |
|--------|-------------|----------|
| Hard rejects for mechanical constraints | Balance, size, tick, single-order, single-market, and single-token position checks reject orders | yes |
| Warnings for aggregate risk | Portfolio exposure, event exposure, drawdown, and liquidity anomalies start as warnings | yes |
| Structured RiskDecision | Risk output is a structured object rather than ad hoc booleans/errors | yes |
| All risk as hard limits immediately | Aggregate risk blocks orders in P0 | no |

**User's choice:** Balance, size, tick, single-order, single-market, and single-token checks are hard rejects. Portfolio exposure, event exposure, drawdown, and liquidity anomalies start as alerts/warnings. Risk output is unified as `RiskDecision`.

**Notes:** P1/P5 can later upgrade warning-class checks into hard blocks.

---

## Phase 3 Minimum Scope

| Priority | Description | Selected |
|----------|-------------|----------|
| P0 | `OrderIntent`, limit/marketable limit/cancel/replace, state machine, depth-driven fills, partial fills, tick/min-size checks, submit/cancel latency, cash/position/fill/fee ledger, conservative marks, realized/unrealized PnL, basic hard risk | yes |
| P1 | GTD expiry, `post_only`, portfolio-level risk, reward estimate, refined queue model | deferred |
| P2 | Market/FOK/FAK, builder fees, OMS/EMS interface, high-fidelity tick-by-tick replay-driven fills | deferred |

**User's choice:** Phase 3 P0 is the minimum implementation scope. P1 and P2 are recorded for later phases or follow-up plans.

**Notes:** This priority split should drive Phase 3 planning granularity.

---

## the agent's Discretion

- Exact enum names and transition labels.
- Exact conservative mark policy details.
- Exact default latency values.
- Exact schema layout, as long as factual ledger and valuation data stay separate.

## Deferred Ideas

- GTD expiry implementation.
- `post_only` enforcement.
- Portfolio-level risk hardening.
- Reward estimate.
- More refined queue model.
- Pure market/FOK/FAK strategy-layer order types.
- Builder fees.
- More complete OMS/EMS interface.
- High-fidelity tick-by-tick replay-driven fills.
