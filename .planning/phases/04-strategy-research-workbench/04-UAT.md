---
status: testing
phase: 04-strategy-research-workbench
source:
  - 04-04-SUMMARY.md
  - 04-05-SUMMARY.md
started: 2026-04-21T09:45:01Z
updated: 2026-04-21T09:45:01Z
---

## Current Test

number: 1
name: Replay Run Bundle
expected: |
  Create a minimal YAML config for Phase 4 and run `StrategyCliService(...).run(..., events=[...])` in `replay` mode. A new run directory should be created under the chosen artifact root. It should contain `manifest.json`, `strategy.log`, and `framework.log`. In `manifest.json`, the mode should be `replay`, the resolved execution config should include defaults such as `post_only: false`, and the configured strategy name/version should be preserved.
awaiting: user response

## Tests

### 1. Replay Run Bundle
expected: Create a minimal YAML config for Phase 4 and run `StrategyCliService(...).run(..., events=[...])` in `replay` mode. A new run directory should be created under the chosen artifact root. It should contain `manifest.json`, `strategy.log`, and `framework.log`. In `manifest.json`, the mode should be `replay`, the resolved execution config should include defaults such as `post_only: false`, and the configured strategy name/version should be preserved.
result: pending

### 2. Realtime Paper Routing
expected: Run the same strategy contract in `realtime_paper` mode with a target-based signal such as `target_position`. The run should produce `order_intents.parquet`, `fills.parquet`, and `risk_decisions.parquet`, showing that signals were translated outside the strategy and routed through the paper exchange boundary.
result: pending

### 3. Runtime Feedback Context
expected: In a realtime paper run that fills at least one order, later strategy callbacks should see updated context for recent fills, risk decisions, cash, and token position. The final artifact set should reflect the filled position rather than the starting state.
result: pending

### 4. Metrics and Manifest Summary
expected: After a realtime paper run completes, `manifest.json` should include a non-empty `metrics_summary` derived from factual artifacts rather than logs, including fields such as `fill_rate`, `max_drawdown`, `reject_count`, and slippage metrics.
result: pending

### 5. Phase 4 Runtime Docs
expected: `README.md` should document the Phase 4 runtime surface clearly: strategy lifecycle (`on_init`, `on_event`, `on_clock`, `on_finish`), target-based signals (`target_exposure` / `target_position`), replay and realtime paper modes, YAML/JSON config, and `manifest.json` artifact bundles.
result: pending

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
