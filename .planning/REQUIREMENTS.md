# Requirements: Polymarket Quant Simulator

**Defined:** 2026-04-18
**Core Value:** 同一套数据与执行抽象必须同时服务历史研究和实时仿真，保证策略从回测到 paper trading 的行为尽量一致。

## v1 Requirements

### Market Universe

- [x] **MKT-01**: 用户可以从 Gamma API 同步活跃 markets、events 和 tags，并建立本地 market universe
- [x] **MKT-02**: 用户可以按类别、到期时间、流动性、成交活跃度和 accepting-orders 状态筛选候选市场
- [x] **MKT-03**: 用户可以查看每个市场的 `conditionId`、Yes/No `tokenId`、tick size、min size、neg-risk、fees 和 rewards 元数据

### Market Data

- [x] **DATA-01**: 用户可以批量抓取并持久化 orderbook、prices、midpoints、spreads 和 price history 数据
- [x] **DATA-02**: 用户可以通过市场 WebSocket 订阅指定 `tokenId` 的 `book`、`price_change`、`best_bid_ask` 和 `last_trade_price` 事件
- [x] **DATA-03**: 用户可以将实时市场事件写入可回放存储，并按时间窗口重建盘口状态
- [ ] **DATA-04**: 用户可以同步 Data API 的 positions、trades 和 activity 数据，用于校准和分析

### Strategy Framework

- [ ] **STRAT-01**: 用户可以基于市场元数据、价格序列和盘口特征编写策略逻辑
- [ ] **STRAT-02**: 用户可以在同一框架下运行历史回放回测与实时 paper 模式
- [ ] **STRAT-03**: 用户可以为策略配置 market universe、信号参数、仓位 sizing 和开平仓规则

### Simulation Execution

- [x] **SIM-01**: 用户可以把策略信号转换为 Polymarket 风格订单意图，包括 side、price、size 和 order type
- [x] **SIM-02**: 用户可以在模拟撮合中得到考虑 tick size、min size、盘口深度、部分成交、撤单和延迟的 fills
- [x] **SIM-03**: 用户可以查看订单生命周期、成交明细、仓位、现金余额以及 realized / unrealized PnL

### Risk & Portfolio

- [x] **RISK-01**: 用户可以配置单市场、单事件和组合级别的风险限额与最大敞口
- [ ] **RISK-02**: 用户可以在市场关闭、不再接单、接近到期、流动性不足或 live 不可用时自动阻止新订单
- [ ] **RISK-03**: 用户可以查看按市场、事件、策略和时间窗口聚合的收益、胜率、回撤和换手指标

### Operations

- [ ] **OPS-01**: 用户可以在一个操作台看到数据连接状态、策略状态、订单、持仓、PnL 和告警
- [ ] **OPS-02**: 用户可以保存实验参数、数据窗口、指标结果和代码版本，以便复现实验
- [ ] **OPS-03**: 用户可以在不修改策略代码的情况下切换 replay、paper 和 live-disabled 运行模式

## v2 Requirements

### Live Bridge

- **LIVE-01**: 用户可以在通过 geoblock、auth、funder 和 allowance 检查后切换到真实 CLOB 下单
- **LIVE-02**: 用户可以运行 shadow mode，对比模拟成交与真实市场演化差异
- **LIVE-03**: 用户可以把奖励、返佣和费率信息纳入市场选择与执行优化

### Advanced Research

- **ADV-01**: 用户可以接入新闻、社媒或事件抽取数据作为额外 alpha 输入
- **ADV-02**: 用户可以建模跨市场关联、互斥和 neg-risk 组合策略
- **ADV-03**: 用户可以运行多策略组合调度和资金分配优化

## Out of Scope

| Feature | Reason |
|---------|--------|
| v1 真实资金自动交易 | 当前目标是先验证数据与仿真 fidelity，避免把合规和密钥管理变成主阻塞项 |
| 多交易所统一路由 | 会稀释 Polymarket-specific 结构和执行细节，降低前期学习效率 |
| 高频做市基础设施 | 与当前单用户、研究优先的项目目标不匹配 |
| 面向外部用户的移动端或 SaaS 产品 | 当前需求是个人量化研究系统，不是商业化产品 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| MKT-01 | Phase 1 | Complete |
| MKT-02 | Phase 1 | Complete |
| MKT-03 | Phase 1 | Complete |
| DATA-01 | Phase 2 | Complete |
| DATA-02 | Phase 2 | Complete |
| DATA-03 | Phase 2 | Complete |
| DATA-04 | Phase 2 | Deferred scope note |
| SIM-01 | Phase 3 | Complete |
| SIM-02 | Phase 3 | Complete |
| SIM-03 | Phase 3 | Complete |
| RISK-01 | Phase 3 | Complete |
| STRAT-01 | Phase 4 | Pending |
| STRAT-02 | Phase 4 | Pending |
| STRAT-03 | Phase 4 | Pending |
| OPS-02 | Phase 4 | Pending |
| RISK-02 | Phase 5 | Pending |
| RISK-03 | Phase 5 | Pending |
| OPS-01 | Phase 5 | Pending |
| OPS-03 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 19
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-18*
*Last updated: 2026-04-19 after Phase 3 verification*
