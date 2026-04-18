# Pitfalls Research

**Verified against official Polymarket docs:** 2026-04-18

| Pitfall | Warning Signs | Prevention Strategy | Phase |
|---------|---------------|---------------------|-------|
| 混淆 `market_id` / `condition_id` / `token_id` | 订阅错频道、订单对不上市场、数据 join 大量为空 | 在 canonical schema 中显式区分三类 ID，并为每类 API 写转换器和单元测试 | Phase 1 |
| 只依赖 REST 轮询做实时策略 | 延迟大、丢失盘口细节、策略行为与真实市场脱节 | 市场数据以 WebSocket 为主，REST 只做 backfill 和健康检查 | Phase 2 |
| 用聚合价格历史替代 L2 级回放 | 回测成交质量过好、滑点严重低估 | 从首日开始持久化原始 WS 事件，并区分“低保真回测”和“高保真回放” | Phase 2 |
| 忽略 tick size / min size / partial fills | 模拟器能成交但真实订单会失败或表现失真 | 在模拟撮合层内置市场约束校验，并使用 market metadata 驱动 | Phase 3 |
| 忽略 fees / rewards / rebates 对策略收益的影响 | maker/taker 策略回测收益与真实结果偏差大 | 把 fee/reward 字段纳入 market registry 和 performance attribution | Phase 3 |
| 把所有市场当成持续可交易 | 策略在 close、restricted 或不接单市场上仍发单 | 在 market selection 和风控中检查 `active/closed/archived/accepting_orders/restricted` | Phase 1 and Phase 5 |
| 过早接入真实下单 | auth、funder、allowance、geoblock 问题反复阻塞主线 | v1 固定为 simulation-first，live bridge 单独建适配层 | Phase 5+ |
| 没有实验复现与版本追踪 | 同一策略结果不可重现，难以定位性能波动 | 记录数据窗口、策略参数、代码版本和指标快照 | Phase 4 |

## Sources

- [Authentication](https://docs.polymarket.com/api-reference/authentication)
- [Quickstart](https://docs.polymarket.com/trading/quickstart)
- [WebSocket Overview](https://docs.polymarket.com/market-data/websocket/overview)
- [Geographic Restrictions](https://docs.polymarket.com/api-reference/geoblock)
