# SuperPolymarket 模拟验收 Checklist

> 目标：判断当前 `SuperPolymarket` 是否已经满足“模拟运行 + paper execution + 自动化报告 + 操作台验证”这条主线。  
> 结论口径：P0 全部通过，才可以认定“满足当前模拟需求”。P1 决定是否适合长期跑；P2 决定是否具备严肃研究平台潜力。

---

## 一、P0 必过项

### 1. 市场同步可正常完成

**目标**  
Phase 1 universe 不是空壳，能实际同步出 active + accepting 市场。

**检查项**

- [ ] `streamlit run src/polymarket_quant/ui/market_universe_app.py` 能打开
- [ ] 点击 `Sync markets` 后 timeline 有完整阶段事件
- [ ] 最终表格出现 active + accepting market rows
- [ ] 每行包含：
  - [ ] `conditionId`
  - [ ] `yes token`
  - [ ] `no token`
- [ ] `source` 列能区分 Gamma / CLOB 来源
- [ ] 同步失败时 UI 会显式失败，而不是假成功

**通过标准**

- 至少一次真实同步成功，且结果非空
- 不出现“UI 显示 pass，但实际一直失败”的错觉

---

### 2. PostgreSQL 数据底座可写入

**目标**  
Phase 2 不是只有设计，实际能落盘。

**检查项**

- [ ] 设置 `DATABASE_URL` 后，backfill 命令能执行
- [ ] realtime collector 能启动
- [ ] PostgreSQL 中确实有：
  - [ ] reference 数据
  - [ ] raw payload
  - [ ] normalized 数据
- [ ] gap fill 发生时有记录，不是静默覆盖
- [ ] market data monitor 页面能看到：
  - [ ] bid/ask
  - [ ] spread
  - [ ] 最近价格曲线
  - [ ] gap-fill 标记

**通过标准**

- 至少 1 个 token 同时存在：
  - 历史 price history
  - 当前 snapshot
  - 最新实时状态

---

### 3. Strategy run 能产出完整 artifact bundle

**目标**  
Phase 4 runtime 不是“能跑”，而是“能留下事实产物”。

**检查项**

- [ ] `StrategyCliService(...).run(...)` 在 `replay` 模式可正常完成
- [ ] 每次 run 生成独立 run 目录
- [ ] run 目录至少有：
  - [ ] `manifest.json`
  - [ ] `signals.parquet`
  - [ ] `strategy.log`
  - [ ] `framework.log`
- [ ] `manifest.json` 中包含：
  - [ ] `run_id`
  - [ ] `strategy_name`
  - [ ] `strategy_version`
  - [ ] `git_commit`
  - [ ] `mode`
  - [ ] `resolved_config`
  - [ ] `universe_snapshot`

**通过标准**

- 任何一次 strategy run 都不是“只在控制台打印了点日志”，而是留下可复盘 bundle

---

### 4. realtime_paper 能走完整 paper execution 链路

**目标**  
验证 signal 真的经过 risk / order / fill，而不是只停在 signal。

**检查项**

- [ ] `realtime_paper` 模式能运行
- [ ] strategy 产生 `Signal`
- [ ] `Signal` 被转换为 `OrderIntent`
- [ ] `PaperExchangeService` 被调用
- [ ] 至少一次 run 中出现：
  - [ ] order
  - [ ] risk_decision
  - [ ] fill 或 reject
- [ ] 产出文件中至少有：
  - [ ] `order_intents.parquet`
  - [ ] `orders.parquet`
  - [ ] `risk_decisions.parquet`
- [ ] 如果有成交，还应有：
  - [ ] `fills.parquet`
  - [ ] `positions.parquet`

**通过标准**

- 证明“策略 → Signal → OrderIntent → risk → paper fill”链路真实存在

---

### 5. 风控阻断确实生效

**目标**  
Phase 5 的安全控制不是摆设。

**检查项**

分别构造以下条件，看是否阻断新单：

- [ ] 市场关闭
- [ ] `accepting_orders = false`
- [ ] `live-disabled` / mode 不可用
- [ ] 临近到期（Critical 阈值）
- [ ] 严重流动性不足
- [ ] 关键连接异常

并检查：

- [ ] 新单被阻断
- [ ] reduce / close 行为没有被误伤
- [ ] `RiskDecision` 中有清晰 reason
- [ ] 操作台上能看到 block 状态
- [ ] 日报/时间线能看到该事件

**通过标准**

- 风控不是“理论上有”，而是能在实际 run 中触发并留下痕迹

---

### 6. Operator Console 首页信息一致

**目标**  
操作台不是“看着像”，而是和 artifacts/运行事实一致。

**检查项**

首页核对：

- [ ] 顶部 mode 状态正确
- [ ] 连接状态正确
- [ ] 策略状态正确
- [ ] 告警摘要与实际一致
- [ ] 新单阻断状态与风控一致

关键明细核对：

- [ ] `Positions / Orders` 与 artifacts 一致
- [ ] `PnL / Exposure` 与 run 结果一致
- [ ] alert timeline 里能看到最近关键事件
- [ ] 不会出现首页显示 healthy，但后台 run 已失败

**通过标准**

- 首页可作为“值班面板”使用，不只是展示页

---

### 7. 自动化 daily run 能闭环完成

**目标**  
Phase 6 真正成立的核心。

**检查项**

- [ ] `python -m polymarket_quant.services.automation_cli config/automation.daily.yaml` 可执行
- [ ] automation run 会生成单独目录
- [ ] automation run 目录包含：
  - [ ] `manifest.json`
  - [ ] `framework.log`
- [ ] 自动化链路按顺序执行：
  - [ ] market sync
  - [ ] realtime health check
  - [ ] strategy batch
  - [ ] report generation
- [ ] strategy artifacts 落到 `data/runs`
- [ ] automation manifest 落到 `data/automation`
- [ ] daily report 落到 `data/reports/daily`

**通过标准**

- 一条命令能跑完 daily automation，并产生 run + report 双产物

---

### 8. graded failure 语义正确

**目标**  
自动化失败策略符合前期设计：不是 fail-fast，也不是盲目 best-effort。

**检查项**

#### 场景 A：market sync 失败

- [ ] health 仍尝试执行
- [ ] strategy batch 被跳过或 gated
- [ ] report generation 仍被尝试
- [ ] manifest 中明确记录 failed / skipped

#### 场景 B：health check 失败

- [ ] 后续链路标记 degraded
- [ ] strategy batch 被跳过
- [ ] report 仍生成

#### 场景 C：某个策略失败

- [ ] 其他策略继续
- [ ] 总 automation run 不直接崩掉
- [ ] 日报中单独标红这个策略

**通过标准**

- 失败处理符合“分级处理”，并能在 automation manifest 与日报中清晰体现

---

### 9. 日报可读且能对上运行事实

**目标**  
日报不是“生成了个文件”，而是内容可信。

**检查项**

日报中至少有：

- [ ] 运行概览
- [ ] realtime 健康摘要
- [ ] 策略运行摘要
- [ ] PnL / drawdown / exposure
- [ ] Critical / Warning 告警
- [ ] 市场同步摘要
- [ ] runs / artifacts 索引

并核对：

- [ ] 时间窗口是“昨日自然日”
- [ ] run 数量和实际 artifacts 对得上
- [ ] 告警数和实际 timeline 对得上
- [ ] 报告中没有“成功”掩盖真实失败

**通过标准**

- 日报能直接拿来做每日运行检查，不需要翻源码才能理解

---

## 二、P1 高价值项

### 10. stress strategy 能形成完整状态循环

**目标**  
验证“更激进策略”真的把系统压起来了。

**检查项**

- [ ] 同一 token 至少经历一次：
  - [ ] enter
  - [ ] add
  - [ ] reduce
  - [ ] exit
- [ ] reason_code 清晰
- [ ] 多次 signal 不会毫无间隔地洪泛
- [ ] 每个 token 最终能进入 completed / done 状态
- [ ] 报表中能看到多阶段行为，而不是只一次 bootstrap

**通过标准**

- 策略足够“激进”来验证系统，但又不至于失控变噪音

---

### 11. metrics summary 不是空壳

**目标**  
run summary 是真实从 artifacts 算出来的。

**检查项**

- [ ] `manifest.json` 里有 `metrics_summary`
- [ ] 至少包含：
  - [ ] `fill_rate`
  - [ ] `reject_count`
  - [ ] `max_drawdown`
  - [ ] `turnover`
  - [ ] `exposure_peak`
- [ ] 这些指标能和 fills / orders / positions 对上

**通过标准**

- metrics 不依赖日志拼凑，而依赖事实产物

---

### 12. preflight / mode switch 语义正确

**目标**  
操作台的 mode 切换不是装饰。

**检查项**

- [ ] 切 mode 前必须做 preflight
- [ ] preflight 能暴露 warning / block reason
- [ ] 没确认前不切换
- [ ] 确认后状态变化可见
- [ ] `live-disabled` 作为保护边界确实有效

**通过标准**

- mode 切换有安全语义，不是直接改个枚举

---

### 13. automation config 真正集中生效

**目标**  
CLI + YAML 边界清晰，不是参数散落。

**检查项**

- [ ] automation config 能声明：
  - [ ] tasks
  - [ ] strategies
  - [ ] artifact root
  - [ ] report output dir
  - [ ] report window
  - [ ] mode
  - [ ] failure_policy
- [ ] 改配置即可改变行为，不必改代码
- [ ] resolved config 会落到 automation manifest

**通过标准**

- 自动化行为来自配置，不来自硬编码

---

## 三、P2 可延后项

### 14. cash ledger / pnl timeline 完整性

**目标**  
验证资金曲线不是空的。

**检查项**

- [ ] `cash_ledger` 不再是空列表
- [ ] `pnl_timeline` 不再是空列表
- [ ] drawdown 能从 timeline 复算
- [ ] report/console 的 pnl 与 timeline 一致

**判断**

- 如果这项不过，项目还能用于“流程模拟”
- 但不能说“账本/收益评估已经成熟”

---

### 15. 长时运行稳定性

**目标**  
不是一次成功，而是连续跑得住。

**检查项**

- [ ] 连续 3 天 daily automation 不崩
- [ ] run 目录不会出现大量残缺 bundle
- [ ] 没有明显资源泄漏
- [ ] report 每天都能产出
- [ ] operator console 状态不会逐渐漂移

**判断**

- 这是从“能跑”进化到“能用”的关键

---

### 16. replay 与 realtime_paper 结果语义接近

**目标**  
同一策略、同一数据，replay 和 paper 不能差得离谱。

**检查项**

- [ ] 同一配置下 replay 与 paper 的 signal 大体一致
- [ ] 差异主要来自 execution 语义，而不是 runtime bug
- [ ] metrics 至少方向一致，不出现完全相反结果

**判断**

- 不过这项不阻断当前流程验证，但会影响后续研究价值

---

### 17. 高保真 market data 回放

**目标**  
验证更细粒度的 replay 研究能力。

**检查项**

- [ ] 自采集 WS 原始事件可重放
- [ ] book state 可按时间顺序回放
- [ ] fill engine 能更贴近真实微观结构

**判断**

- 当前阶段可延后
- 但后续如果要做严肃策略研究，这项必须补

---

## 四、最终验收结论模板

### P0 必过项

- [ ] 1. 市场同步
- [ ] 2. PostgreSQL 数据底座
- [ ] 3. Strategy artifact bundle
- [ ] 4. realtime_paper 执行链路
- [ ] 5. 风控阻断
- [ ] 6. Operator Console 一致性
- [ ] 7. automation daily 闭环
- [ ] 8. graded failure
- [ ] 9. 日报可读可信

**P0 结论**

- P0 全部通过：可以认定“满足当前模拟需求”
- P0 有 1~2 项未通过：可用，但不能说闭环成立
- P0 有 3 项以上未通过：还只是阶段性 demo

---

### P1 高价值项

- [ ] 10. stress strategy 完整循环
- [ ] 11. metrics summary 可信
- [ ] 12. preflight / mode switch
- [ ] 13. automation config 集中生效

**P1 结论**

- 通过越多，越接近“能长期跑的 simulation platform”

---

### P2 可延后项

- [ ] 14. cash ledger / pnl timeline
- [ ] 15. 长时运行稳定性
- [ ] 16. replay 与 paper 接近
- [ ] 17. 高保真回放

**P2 结论**

- 这些决定它是不是“严肃研究平台”

---

## 五、当前仓库预判

基于当前代码与 README 的结构，预判如下。

### 大概率已通过

- 1. 市场同步
- 3. Strategy artifact bundle
- 4. realtime_paper 执行链路
- 7. automation daily 闭环
- 8. graded failure
- 9. 日报输出
- 13. automation config 集中生效

### 需要重点验证

- 5. 风控阻断是否真的全命中
- 6. Operator Console 与事实是否完全一致
- 10. stress strategy 是否真的形成完整 cycle
- 11. metrics summary 是否足够可信

### 最可疑的薄弱项

- 14. cash ledger / pnl timeline 完整性

---

## 六、验收建议

优先执行顺序建议：

1. 先跑 P0-7：确认 automation daily 闭环能跑完
2. 再查 P0-3 / P0-4：确认 strategy artifacts 与 paper execution 链路真实存在
3. 再测 P0-5 / P0-8：故意制造失败和阻断场景
4. 最后查 P1-10 / P1-11：验证 stress strategy 与 metrics summary 是否可信
5. P2-14 单独立项处理，不要混在当前模拟闭环验收里
