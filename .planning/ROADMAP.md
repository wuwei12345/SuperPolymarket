# Roadmap: Polymarket Quant Simulator

**Created:** 2026-04-18
**Granularity:** Standard
**Execution:** Parallel
**Coverage:** 19 / 19 v1 requirements mapped

## Summary

| # | Phase | Goal | Requirements | Success Criteria | UI hint |
|---|-------|------|--------------|------------------|---------|
| 1 | Market Universe & Metadata | 建立可信的 Polymarket 市场目录和统一 ID 映射 | MKT-01, MKT-02, MKT-03 | 3 | no |
| 2 | Historical & Real-Time Data Platform | 建立历史抓取、实时流采集与回放基础设施 | DATA-01, DATA-02, DATA-03, DATA-04 | 4 | no |
| 3 | Simulation Exchange & Portfolio Ledger | 建立与 Polymarket 语义一致的模拟执行和账户账本 | SIM-01, SIM-02, SIM-03, RISK-01 | 4 | no |
| 4 | Strategy Research Workbench | 建立可复现的策略开发、回测与实验框架 | STRAT-01, STRAT-02, STRAT-03, OPS-02 | 4 | no |
| 5 | Operator Console & Safety Controls | 建立监控、风控和模式切换能力 | RISK-02, RISK-03, OPS-01, OPS-03 | 4 | yes |

## Phase Details

## Phase 1: Market Universe & Metadata

**Goal:** 把 Gamma 与 CLOB 的市场元数据整理成一个可查询、可验证的 canonical market universe，为后续数据采集和策略筛选打底。

**Requirements:** MKT-01, MKT-02, MKT-03

**Success Criteria**
1. 系统可以定期同步 active markets、events、tags，并落地到本地 registry。
2. 每个市场都能稳定映射到 `conditionId` 与 Yes/No `tokenId`。
3. 用户可以基于 category、liquidity、endDate、restricted、acceptingOrders 等条件筛选市场 universe。

**UI hint**: no
**Status**: Complete — verified 2026-04-18

## Phase 2: Historical & Real-Time Data Platform

**Goal:** 建立 public data ingestion、WebSocket collector 和 replay substrate，让系统既能 backfill，也能做实时驱动与事后重放。

**Requirements:** DATA-01, DATA-02, DATA-03, DATA-04

**Success Criteria**
1. 系统可以批量抓取并持久化书本、价格、midpoint、spread 和 price history。
2. 市场 WebSocket 采集器可以订阅多个 `tokenId`，断线后自动恢复，并持续写入原始事件。
3. 用户可以按时间窗口重建盘口状态，并用于调试或回测。
4. Data API 的 trades、positions、activity 数据可以作为分析和校准数据接入。

**UI hint**: no
**Status**: Complete — verified 2026-04-18

## Phase 3: Simulation Exchange & Portfolio Ledger

**Goal:** 建立一个贴近 Polymarket 订单语义的 paper exchange，并让组合账本和风险限制可以真实反映策略行为。

**Requirements:** SIM-01, SIM-02, SIM-03, RISK-01

**Success Criteria**
1. 策略信号可以被标准化为 side、price、size、order type 等订单意图。
2. 模拟撮合会考虑 tick size、min size、depth、partial fills、cancel 和 latency。
3. 系统可以跟踪订单生命周期、持仓、现金和 realized/unrealized PnL。
4. 风险限额可以在下单前阻止超限订单，并在组合视角展示暴露。

**UI hint**: no
**Status**: Planned — 5 plans created 2026-04-19

## Phase 4: Strategy Research Workbench

**Goal:** 建立研究者日常使用的策略开发与实验工作台，让同一套策略逻辑可以在历史和实时纸面环境中运行。

**Requirements:** STRAT-01, STRAT-02, STRAT-03, OPS-02

**Success Criteria**
1. 用户可以基于标准化行情、盘口特征和市场元数据编写策略。
2. 同一份策略逻辑可以在 replay backtest 和实时 paper mode 下运行。
3. 用户可以配置 universe、参数、sizing 和开平仓规则，而不是把这些硬编码在策略里。
4. 每次实验都保存参数、数据窗口、版本和关键结果，方便复现。

**UI hint**: no
**Status**: Pending

## Phase 5: Operator Console & Safety Controls

**Goal:** 给操作者一个能看清系统健康、策略运行和风险暴露的控制台，并在模式切换和风险阻断上建立明确保护。

**Requirements:** RISK-02, RISK-03, OPS-01, OPS-03

**Success Criteria**
1. 用户可以在一个界面看到数据连接、策略状态、订单、持仓、PnL 和告警。
2. 系统会在市场关闭、不接单、临近到期或流动性不达标时阻止新增订单。
3. 用户可以按市场、事件、策略和时间窗口查看收益、回撤、胜率和换手。
4. 用户可以在 replay、paper 和 live-disabled 模式间切换，而不需要修改策略代码。

**UI hint**: yes
**Status**: Pending

## Notes

- v1 明确是 simulation-first；真实下单桥接被保留到 v2。
- 若后续确认要做 reward/rebate 优化或 live bridge，可在当前里程碑之后新增 Phase 5.1 / Phase 6。

---
*Last updated: 2026-04-19 after Phase 3 planning*
