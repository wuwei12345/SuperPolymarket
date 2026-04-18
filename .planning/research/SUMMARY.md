# Research Summary

**Date:** 2026-04-18

## Feasibility

可行。Polymarket 官方 API 已经提供了构建模拟量化交易系统所需的大部分基础面：

- 市场发现：Gamma API
- 持仓/成交/活动分析：Data API
- 盘口、价格、价格历史与交易协议：CLOB API
- 实时事件流：Market/User WebSocket
- 官方客户端：TypeScript / Python / Rust

对当前项目最关键的结论是：数据和协议层已经足够完善，真正的难点不在“能不能接到 API”，而在“如何建立高保真、可回放、可复现实验的数据与执行体系”。

## Recommended Direction

1. Python-first
2. Simulation-first
3. Event-driven architecture
4. Canonical market schema from day one
5. Persist raw WebSocket events for replay and debugging

## Table Stakes To Build First

- Canonical market universe
- Historical + real-time market data ingestion
- Replayable event log
- Polymarket-style simulation exchange
- Strategy runtime with reproducible experiments
- Dashboard and risk controls

## Main Risks

- Historical L2 fidelity is not free; you need to self-capture live events
- ID mismatches across Gamma/CLOB/Data can quietly corrupt joins
- Execution realism collapses if tick/min size, depth, latency, and fees are ignored
- Live trading later will require auth, geoblock, funder, and allowance handling

## Sources

- [Introduction](https://docs.polymarket.com/api-reference/introduction)
- [Authentication](https://docs.polymarket.com/api-reference/authentication)
- [Clients & SDKs](https://docs.polymarket.com/api-reference/clients-sdks)
- [Rate Limits](https://docs.polymarket.com/api-reference/rate-limits)
- [WebSocket Overview](https://docs.polymarket.com/market-data/websocket/overview)
- [Geographic Restrictions](https://docs.polymarket.com/api-reference/geoblock)
