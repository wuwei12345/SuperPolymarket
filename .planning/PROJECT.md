# Polymarket Quant Simulator

## What This Is

基于 Polymarket 官方 Gamma / Data / CLOB / WebSocket / Subgraph 接口，构建一套面向自用研究与模拟交易的量化系统。系统先解决“发现哪些市场可交易、如何稳定拉取和回放盘口、如何在不下真实单的前提下评估策略”的问题，再为后续 paper/live bridge 预留兼容层。目标用户是希望做 Polymarket 策略研究、回测、实时仿真和组合监控的个人量化开发者。

## Core Value

同一套数据与执行抽象必须同时服务历史研究和实时仿真，保证策略从回测到 paper trading 的行为尽量一致。

## Requirements

### Validated

- [x] 统一接入 Polymarket 官方 API，并建立可查询的 market universe — Validated in Phase 1
- [x] 建立历史数据、实时流、重放链路三者一致的数据底座 — Validated in Phase 2 for public market data and research-grade replay

### Active

- [ ] 建立 Polymarket 风格的模拟撮合、仓位、PnL 与风险引擎
- [ ] 建立可复现的策略研究、回测、实时仿真运行框架
- [ ] 提供面向操作者的监控、告警与实验管理能力

### Out of Scope

- v1 直接下真实资金订单 — 当前目标是先验证策略、数据和仿真 fidelity，避免合规、资金和密钥风险
- v1 多交易所抽象层 — 先把 Polymarket 的市场结构、API 语义和执行细节吃透
- v1 超低延迟/HFT 基础设施 — 官方 API + 公网延迟决定这不是第一阶段的核心收益点
- v1 面向外部用户的 SaaS / 移动端产品 — 当前场景是个人量化研究与操盘

## Context

截至 2026-04-18 核对的官方文档表明，Polymarket 暴露了三类主 API：Gamma API 负责市场/事件发现，Data API 负责 positions / trades / activity 等分析数据，CLOB API 负责 orderbook、价格、price history 及交易操作。官方同时提供 Market/User WebSocket，以及 TypeScript、Python、Rust 三套官方客户端。

这意味着“模拟量化交易系统”在数据面是可行的：公开接口已经覆盖 market discovery、盘口、成交、价格历史、持仓与活动数据，足够建立 market universe、行情采集、回放和仿真执行。需要明确的是，官方文档强调实时盘口应优先用 WebSocket，而不是持续 REST 轮询；如果后续要做高保真回测，不能只依赖简单 price history，必须从项目第一天开始自采并持久化 L2 级别实时数据。

交易面也具备后续扩展空间：官方文档说明 CLOB 交易接口采用 L1/L2 双层认证，支持下单、撤单、订单查询和用户 WebSocket，但这部分会受地理限制、签名类型、funder address、allowance 和余额约束影响。由于当前项目明确是“模拟”，v1 会只做 paper/simulated execution；live bridge 放到后续阶段，并保留与官方认证/订单模型兼容的接口。

## Constraints

- **API Surface**: 必须优先使用 Polymarket 官方 API 与官方 SDK — 这样能减少签名细节和协议漂移带来的维护成本
- **Execution Scope**: v1 只做模拟与 paper-first 执行 — 用户当前需求是确认可行性并建立研究系统，而不是真仓交易
- **Compliance**: live bridge 前必须显式 geoblock 检查与密钥隔离 — 官方文档明确说明受限地区下单会被拒绝
- **Historical Fidelity**: 回测不能只依赖聚合价格历史 — 高频率成交和盘口深度变化必须靠实时订阅自采
- **Canonical Schema**: 全系统必须以 `conditionId`、`tokenId`、`market/event metadata` 的规范映射为中心 — 否则不同 API 的 ID 体系容易错位

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 项目首版只覆盖 Polymarket | 用户目标就是验证 Polymarket 量化可行性，过早抽象多交易所只会稀释核心问题 | — Pending |
| 全量接入官方 Gamma/Data/CLOB/WebSocket/Subgraph 能力，但 v1 只开放模拟执行 | 数据面已经足够支撑策略研究；真实执行牵涉合规和账户控制，应该后置 | — Pending |
| 采用 Python-first 架构 | 官方存在 Python 客户端，且研究、特征工程、回测生态更适合 Python | — Pending |
| 采用 event-driven 数据与执行模型 | Polymarket 的盘口、成交和用户订单更新天然是事件流，适合统一回放与实时仿真 | — Pending |
| 从第一阶段开始保存原始 WebSocket 事件与标准化表 | 高保真回测和问题排查都依赖可重放的原始事实流 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition**:
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone**:
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-18 after Phase 2 verification*
