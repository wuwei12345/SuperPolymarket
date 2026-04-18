# Phase 1: Market Universe & Metadata — Specification

**Created:** 2026-04-18
**Ambiguity score:** 0.11 (gate: ≤ 0.20)
**Requirements:** 5 locked

## Goal

交付一个可手动触发同步的 Polymarket market universe 基础能力，把 `active + accepting orders` 市场规范化入库，并通过一个以数据表为主的 Web 页面直观看到结果、同步过程、失败重试和字段来源。

## Background

当前仓库只有 GSD 规划文档和项目说明，没有任何业务代码、数据模型、同步任务、API 接口或前端页面。`ROADMAP.md` 已经锁定了本阶段的核心目标是建立 canonical market universe，并要求系统能够同步活跃市场、稳定映射 `conditionId` 和 Yes/No `tokenId`，并支持按市场元数据筛选。用户进一步明确了本阶段需要一个只服务于 Phase 1 验收的轻量 Web 页面，重点是表格化展示市场列表和筛选结果，并可追踪同步过程与字段来源。

## Requirements

1. **Active universe sync**: 系统只同步并展示同时满足 `active = true` 且 `accepting orders = true` 的市场。
   - Current: 没有任何市场同步逻辑，也没有本地 market universe 数据
   - Target: 系统可以从官方数据源拉取市场并产出只包含 `active + accepting orders` 市场的 canonical market universe
   - Acceptance: 运行一次同步后，本地数据集中每条市场记录都满足 `active = true` 且 `accepting orders = true`，且不存在 closed/archived-only 市场

2. **Canonical ID mapping**: 每条市场记录必须包含可验证的 `conditionId` 与 Yes/No `tokenId` 映射。
   - Current: 项目内没有任何 `conditionId`、`tokenId` 或 canonical market schema
   - Target: 每条 market universe 记录都能关联到 `conditionId`、Yes token id、No token id，以及必要的市场元数据
   - Acceptance: 抽样检查任意 10 条记录时，均能看到完整 `conditionId` + 2 个 token id，且字段不为空

3. **Filterable market table**: 提供一个以数据表为主的 Web 页面，能展示市场列表并支持筛选和排序。
   - Current: 没有任何 Web 页面、表格 UI 或市场查询界面
   - Target: 用户可以在浏览器中查看市场列表，并按 category、liquidity、end date、restricted 状态等字段筛选/排序
   - Acceptance: 页面可加载表格；至少支持 3 个筛选维度和 2 个排序字段；筛选后行数和结果集合发生可验证变化

4. **Visible sync process**: Web 页面必须展示同步过程、日志、失败重试和最终状态。
   - Current: 没有同步任务，也没有日志展示或失败反馈
   - Target: 用户手动触发同步时，可以看到开始、进行中、重试、成功/失败等过程信息，以及最近一次运行结果
   - Acceptance: 在一次正常同步和一次模拟失败/重试场景下，页面都能显示时间顺序明确的过程日志和最终状态

5. **Field source traceability**: Web 页面必须能明确看出关键列来自 Gamma 还是 CLOB。
   - Current: 没有来源追踪，也没有字段级来源展示
   - Target: 表格中关键字段或其辅助说明可明确标识数据来源，至少区分 Gamma 与 CLOB 两类来源
   - Acceptance: 页面上可验证看到关键字段来源标识；用户可以指出某列来自 Gamma、某列来自 CLOB，而不需要读代码

## Boundaries

**In scope:**
- 构建只覆盖 `active + accepting orders` 市场的 canonical market universe
- 为 market universe 建立 `conditionId` 与 Yes/No `tokenId` 映射
- 提供一个只读的 Web 表格页面用于查看、筛选、排序和验收市场数据
- 在页面中展示同步过程、日志、失败重试和最近一次同步结果
- 在页面或相应列说明中标记关键字段的数据来源（Gamma / CLOB）

**Out of scope:**
- 单个市场详情面板或 drill-down 页面 — 用户已明确本阶段先只做表格
- 实时 WebSocket 数据流展示 — 这是 Phase 2 的实时数据平台范围
- 持仓、PnL、订单或策略相关可视化 — 这些属于后续策略/运营阶段
- 真实交易下单、账户认证或钱包接入 — 超出 Phase 1 的 market universe 范围
- 完整运营控制台或多页面后台 — 当前页面只服务本阶段验收，不扩展为全量 dashboard

## Constraints

- 数据范围必须默认限制为 `active + accepting orders` 市场，不能把 closed 或仅 active 但不可下单的市场混入默认结果
- 页面必须以表格为主，不做卡片流、详情页优先或复杂多栏工作台
- 来源追踪必须直接体现在页面可见信息中，不能要求用户通过 API 响应或开发者工具才能识别
- 同步过程必须可见，至少覆盖开始、重试、成功/失败、完成时间这几类事件
- 本阶段页面是只读验收界面，不承担编辑、批量操作或交易动作

## Acceptance Criteria

- [ ] 手动触发一次同步后，系统只产出并展示 `active + accepting orders` 市场
- [ ] 每条市场记录都包含 `conditionId`、Yes token id、No token id
- [ ] Web 页面以表格形式展示市场列表，并支持至少 3 个筛选维度和 2 个排序字段
- [ ] 页面可以看到同步开始、重试、成功/失败和最近完成时间
- [ ] 页面可以明确识别关键字段来源于 Gamma 还是 CLOB
- [ ] 本阶段不包含详情面板、交易动作、PnL 视图或实时流可视化

## Ambiguity Report

| Dimension           | Score | Min   | Status | Notes |
|---------------------|-------|-------|--------|-------|
| Goal Clarity        | 0.92  | 0.75  | ✓      | 交付物已收敛为 canonical universe + read-only table page |
| Boundary Clarity    | 0.91  | 0.70  | ✓      | 用户明确排除了详情面板，并限定只读表格与过程观测 |
| Constraint Clarity  | 0.80  | 0.65  | ✓      | active+accepting、表格优先、来源可见、过程可见均已锁定 |
| Acceptance Criteria | 0.86  | 0.70  | ✓      | 已转成 6 条可验证的 pass/fail 条目 |
| **Ambiguity**       | 0.11  | ≤0.20 | ✓      | 可进入 discuss-phase 锁定 HOW |

## Interview Log

| Round | Perspective | Question summary | Decision locked |
|-------|-------------|------------------|-----------------|
| 1 | Researcher | Phase 1 是否需要可视化验收页面 | 需要一个 Web 页面直观看到过程和结果 |
| 1 | Simplifier | 页面主要看什么 | 以市场列表和筛选结果为核心 |
| 1 | Simplifier | 页面形态更像什么 | 采用数据表为主的展示方式，适合筛选和排序 |
| 2 | Boundary Keeper | 过程可见到什么程度 | 必须显示逐步过程、日志、失败重试和数据来源 |
| 2 | Boundary Keeper | 默认市场范围是什么 | 默认只看 `active + accepting orders` 市场 |
| 2 | Boundary Keeper | 是否需要详情面板 | 本阶段不要详情面板，只做表格 |
| 2 | Seed Closer | 完成标准是什么 | 除结果外，还要在页面上明确字段来自 Gamma 还是 CLOB |

---
*Phase: 01-market-universe-metadata*
*Spec created: 2026-04-18*
*Next step: $gsd-discuss-phase 1 — implementation decisions (how to build what's specified above)*
