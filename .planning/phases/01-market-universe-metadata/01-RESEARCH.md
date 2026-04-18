# Phase 01 — Research: Market Universe & Metadata

**Created:** 2026-04-18
**Status:** Research complete

## Research Question

What do we need to know to plan Phase 1 well: syncing `active + accepting orders` Polymarket markets, normalizing `conditionId`/Yes-No `tokenId` mappings, and presenting a read-only table UI with sync timeline and source provenance?

## Source Findings

### Polymarket API surfaces

- Gamma API is the right source for human-readable market/event metadata such as market question, category-like metadata, dates, volume/liquidity fields, active/closed state, and `clobTokenIds`.
- CLOB `/simplified-markets` is the right source for CLOB-native `condition_id`, `tokens`, `active`, `closed`, `archived`, and `accepting_orders`.
- CLOB market data endpoints and WebSocket channels exist, but Phase 1 must not consume live WebSocket market data; that belongs to Phase 2.

### Identifier semantics

- Gamma and CLOB expose overlapping but differently named identifiers.
- Canonical model should preserve source-specific IDs and normalized IDs:
  - `condition_id`
  - `yes_token_id`
  - `no_token_id`
  - Gamma fields such as `id`, `question`, `category`, `endDate`, `liquidity`
  - CLOB fields such as `condition_id`, `tokens`, `rewards`, `accepting_orders`
- A market is valid for Phase 1 only when it has a non-empty `condition_id` and exactly two non-empty token IDs for Yes/No outcomes.

### Rate limits and sync design

- Official docs publish high but finite rate limits. Gamma `/markets` has a lower documented limit than broad CLOB general endpoints.
- Sync should avoid unnecessary fan-out calls in Phase 1. Prefer:
  1. Gamma market listing fetch
  2. CLOB simplified market listing fetch with cursor pagination
  3. Local normalization/join
- Use explicit retry with bounded attempts and timeline events so the UI can show retries and failures.

### UI implications

- Phase 1 has no existing app code or design system.
- Project research recommends Python-first and Streamlit initially for operator UI.
- UI-SPEC locks a Streamlit-style internal page with left filters, right table, bottom timeline log, and no detail panel.

## Recommended Technical Approach

### App shape

Use a single Python package with these responsibilities:

- `src/polymarket_quant/domain/market.py` — canonical Pydantic models and source provenance structs
- `src/polymarket_quant/adapters/polymarket.py` — Gamma/CLOB HTTP clients
- `src/polymarket_quant/services/market_sync.py` — retrying sync orchestration and normalization
- `src/polymarket_quant/storage/market_store.py` — local SQLite persistence for Phase 1
- `src/polymarket_quant/ui/market_universe_app.py` — Streamlit-style UI entrypoint
- `tests/` — unit tests for normalization, filtering, retry logging, and source provenance

Use SQLite for Phase 1 because the registry is small, local, and read-heavy. This does not contradict the project-level direction toward PostgreSQL/Timescale later; Phase 1 should keep operational overhead low while establishing data contracts.

### Source provenance

Every table column shown in the UI should map to a source label:

| UI column | Canonical field | Source |
|-----------|-----------------|--------|
| question | `question` | Gamma |
| category | `category` | Gamma |
| liquidity | `liquidity` | Gamma |
| endDate | `end_date` | Gamma |
| conditionId | `condition_id` | Gamma+CLOB |
| yes token | `yes_token_id` | CLOB |
| no token | `no_token_id` | CLOB |
| source | `source_labels` | Normalizer |

### Validation Architecture

Phase 1 can be validated with pytest without live API dependency:

- Mock Gamma `/markets` responses
- Mock CLOB `/simplified-markets` paginated responses
- Verify only `active + accepting orders` markets survive normalization
- Verify invalid records missing condition/token IDs are excluded or counted as errors
- Verify sync retry events are emitted for simulated transient failures
- Verify UI module exposes required labels, default columns, filters, and timeline copy

Live API smoke checks can remain manual/non-blocking for this phase because deterministic tests should not depend on current Polymarket market availability.

## Risks and Guardrails

- **ID mismatch risk:** Never join on question text. Join on `condition_id` and/or token ID fields.
- **Silent invalid rows risk:** Markets missing complete IDs must not silently appear as valid table rows.
- **Scope creep risk:** Do not add orderbook, WebSocket streaming, position data, PnL, wallet auth, or trading actions.
- **UI drift risk:** The UI must remain table-first. Do not replace the table with cards or a full dashboard.

## Sources

- [Polymarket API Introduction](https://docs.polymarket.com/api-reference/introduction)
- [Get simplified markets](https://docs.polymarket.com/api-reference/markets/get-simplified-markets)
- [Rate Limits](https://docs.polymarket.com/quickstart/introduction/rate-limits)
- [WebSocket Overview](https://docs.polymarket.com/market-data/websocket/overview)
- [Market Channel](https://docs.polymarket.com/developers/CLOB/websocket/market-channel)

## RESEARCH COMPLETE
