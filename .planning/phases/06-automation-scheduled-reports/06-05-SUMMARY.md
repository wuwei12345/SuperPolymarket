---
phase: 06-automation-scheduled-reports
plan: 05
subsystem: automation-workflow
tags: [cli, cron, config, docs]
requires:
  - phase: 06-01
    provides: [automation config]
  - phase: 06-02
    provides: [AutomationRunner]
  - phase: 06-03
    provides: [ReportBuilder]
  - phase: 06-04
    provides: [report outputs]
provides:
  - Automation CLI entrypoint
  - Checked-in daily automation config
  - README cron workflow documentation
affects: [operator-workflow, onboarding]
tech-stack:
  added: []
  patterns: [one-shot-cli, config-driven-daily-run]
key-files:
  created:
    - src/polymarket_quant/services/automation_cli.py
    - config/automation.daily.yaml
    - config/strategy.daily.yaml
    - tests/unit/test_automation_cli.py
  modified:
    - README.md
    - src/polymarket_quant/services/__init__.py
key-decisions:
  - "Manual and cron-triggered runs use the same one-shot CLI path."
  - "Sample config stays in `realtime_paper` mode and does not imply live trading."
patterns-established:
  - "README documents cron as the external scheduler boundary for recurring automation."
requirements-completed: [AUTO-01, AUTO-02, AUTO-03]
duration: 0 min
completed: 2026-04-22
---

# Phase 6 Plan 05: Automation Workflow Summary

**Operator-facing CLI, sample config, and cron documentation**

## Accomplishments

- Added `AutomationCliService` and a `python -m` entrypoint for one-shot automation execution.
- Added checked-in sample configs for a daily automation job and a minimal `realtime_paper` strategy run.
- Documented manual invocation, output locations, and `cron` usage in the README.
- Exported the new automation services and added CLI/docs coverage tests.

## Task Commits

1. **Tasks 1-2: Automation CLI, config, docs** - pending phase commit

## Deviations from Plan

- None.

## Self-Check: PASSED

- `pytest tests/unit/test_automation_cli.py -q` -> 3 passed.
- `python -m polymarket_quant.services.automation_cli --help` returned the expected one-shot CLI usage.
- README includes `cron` guidance and preserves the `realtime_paper` boundary.

---
*Phase: 06-automation-scheduled-reports*
*Completed: 2026-04-22*
