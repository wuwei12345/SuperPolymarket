# Phase 1: Market Universe & Metadata - Context

**Gathered:** 2026-04-18
**Status:** Ready for planning

<domain>
## Phase Boundary

本阶段交付一个只覆盖 `active + accepting orders` 市场的 canonical market universe，以及一个只读 Web 页面用于查看市场列表、筛选排序结果、同步过程和字段来源。它是后续数据平台与策略系统的入口和验收界面，不承担交易、PnL、详情页或实时流展示。

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**5 requirements are locked.** See `01-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `01-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):**
- 构建只覆盖 `active + accepting orders` 市场的 canonical market universe
- 为 market universe 建立 `conditionId` 与 Yes/No `tokenId` 映射
- 提供一个只读的 Web 表格页面用于查看、筛选、排序和验收市场数据
- 在页面中展示同步过程、日志、失败重试和最近一次同步结果
- 在页面或相应列说明中标记关键字段的数据来源（Gamma / CLOB）

**Out of scope (from SPEC.md):**
- 单个市场详情面板或 drill-down 页面 — 用户已明确本阶段先只做表格
- 实时 WebSocket 数据流展示 — 这是 Phase 2 的实时数据平台范围
- 持仓、PnL、订单或策略相关可视化 — 这些属于后续策略/运营阶段
- 真实交易下单、账户认证或钱包接入 — 超出 Phase 1 的 market universe 范围
- 完整运营控制台或多页面后台 — 当前页面只服务本阶段验收，不扩展为全量 dashboard

</spec_lock>

<decisions>
## Implementation Decisions

### Page layout
- **D-01:** 页面采用三段式布局：左侧固定筛选区，右侧主表格区，底部可展开/收起的日志区。
- **D-02:** 主体验收焦点是表格和同步过程，不做右侧详情抽屉或二级详情区。

### Table presentation
- **D-03:** 首屏默认表格列包含 `question`、`category`、`liquidity`、`endDate`、`conditionId`、`yes/no token`、`来源标签`。
- **D-04:** 该页面是数据表优先的运维/验收视图，规划时应优先保证排序、筛选、密度和可扫读性，而不是视觉卡片化。

### Logs and sync feedback
- **D-05:** 同步过程采用时间线日志呈现，而不是终端风格纯文本流或状态卡片为主。
- **D-06:** 日志区默认可见最近状态，但必须支持手动展开/收起，避免挤压主表格。
- **D-07:** 时间线日志中必须能看到开始、重试、成功/失败、完成时间，以及对应的数据来源或步骤标签。

### Filtering and interaction
- **D-08:** 筛选是即时生效的，不增加“Apply filters”确认按钮。
- **D-09:** 该页面首先服务于快速筛选 active market universe，因此交互要偏分析台而不是表单式流程。

### the agent's Discretion
- 具体筛选控件形式（下拉、组合筛选、范围输入）
- 表格分页/虚拟滚动的技术实现
- 日志时间线的视觉细节、颜色和图标策略
- 来源标签是列内 tag、tooltip 还是列头辅助说明，只要页面上可直接识别

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase definition
- `.planning/phases/01-market-universe-metadata/01-SPEC.md` — Locked requirements, boundaries, and acceptance criteria for Phase 1
- `.planning/ROADMAP.md` — Phase 1 goal and success criteria in milestone context
- `.planning/REQUIREMENTS.md` — MKT-01, MKT-02, MKT-03 requirements that this phase must satisfy

### Project constraints
- `.planning/PROJECT.md` — Project-level constraints, core value, and v1 simulation-first boundary
- `.planning/STATE.md` — Current project status and active phase reference

### Research context
- `.planning/research/SUMMARY.md` — Feasibility summary and build-order guidance
- `.planning/research/ARCHITECTURE.md` — Recommended component boundaries and canonical entity model
- `.planning/research/PITFALLS.md` — ID mapping, source-of-truth, and market-state pitfalls relevant to Phase 1

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- No existing application code yet — this phase will establish the first concrete data and UI patterns

### Established Patterns
- Planning artifacts indicate Python-first, simulation-first, event-driven architecture
- No prior UI or data-layer code patterns exist in the repository yet

### Integration Points
- New implementation should create the initial canonical market registry, sync entry point, and Phase 1 read-only Web view
- Output of this phase becomes the input substrate for Phase 2 historical/real-time data ingestion

</code_context>

<specifics>
## Specific Ideas

- 页面结构明确为“左侧筛选 + 右侧表格 + 底部日志”
- 日志区可以打开收起
- 表格首屏必须直接看到 `question`、`category`、`liquidity`、`endDate`、`conditionId`、`yes/no token`、来源标签
- 日志以时间线形式展示
- 筛选即时生效

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-market-universe-metadata*
*Context gathered: 2026-04-18*
