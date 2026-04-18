# Stack Research

**Verified against official Polymarket docs:** 2026-04-18

## Source-Backed Facts

- Polymarket currently exposes three primary API surfaces:
  - Gamma API: markets, events, tags, search, public metadata
  - Data API: positions, trades, activity, holders, analytics
  - CLOB API: orderbook, prices, spreads, price history, trading operations
- Official clients exist in TypeScript, Python, and Rust, and the docs explicitly state all three support the full CLOB API.
- Trading operations require CLOB authentication, while Gamma/Data and CLOB read endpoints are public.
- Real-time orderbook and trade updates are available through WebSocket market/user channels.

## Recommended Stack

The choices below are design recommendations inferred from the official API shape and the needs of a quant simulator.

| Layer | Choice | Why | Confidence |
|-------|--------|-----|------------|
| Core language | Python 3.12 | Best fit for research, backtesting, analytics, and the official `py-clob-client-v2` client | High |
| Polymarket access | Official Python CLOB client + direct `httpx` calls for Gamma/Data | Keep authenticated trading semantics aligned with official client while using lightweight public REST calls elsewhere | High |
| Streaming | `websockets` + async ingestion workers | Market/user channels are event-driven; async is a natural fit | High |
| API/service layer | FastAPI | Simple query/control plane for internal services and dashboard consumers | Medium |
| Operational storage | PostgreSQL 16 + Timescale-style time-series schema | Strong relational model for orders/positions plus indexed time-series reads | Medium |
| Research storage | Parquet + DuckDB | Cheap local replay, fast batch analytics, reproducible snapshots | High |
| Data validation | Pydantic v2 | Useful for normalizing mismatched Gamma/Data/CLOB payloads | High |
| Retry/resilience | `tenacity` + explicit reconnect logic | Official endpoints are rate-limited and WebSocket sessions need resilient reconnects | High |
| Operator UI | Streamlit initially, optional richer UI later | Single-user quant workflow benefits from Python-native UI first | Medium |

## What Not To Use Yet

- Heavy distributed infra (Kafka, Flink, multi-service event bus): too much operational cost for a first single-user simulator
- Multi-exchange abstraction: it will blur Polymarket-specific details like `conditionId`, `tokenId`, binary market microstructure, neg-risk, and reward metadata
- Live wallet automation in v1: current project goal is research fidelity, not deployment speed

## Design Notes

- Use a canonical identifier model:
  - `event_id` / `market_id` from Gamma
  - `condition_id` from market/CLOB context
  - `token_id` for Yes/No tradeable assets
- Separate immutable raw event capture from normalized tables used by strategies.
- Make the simulator consume the same normalized event stream that live mode would consume later.

## Sources

- [Introduction](https://docs.polymarket.com/api-reference/introduction)
- [Authentication](https://docs.polymarket.com/api-reference/authentication)
- [Clients & SDKs](https://docs.polymarket.com/api-reference/clients-sdks)
- [WebSocket Overview](https://docs.polymarket.com/market-data/websocket/overview)
- [Rate Limits](https://docs.polymarket.com/api-reference/rate-limits)
