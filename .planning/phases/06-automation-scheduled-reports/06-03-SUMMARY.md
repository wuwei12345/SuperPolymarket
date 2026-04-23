---
phase: 06-automation-scheduled-reports
plan: 03
subsystem: report-builder
tags: [reports, markdown, operator-queries, calendar-window]
requires:
  - phase: 06-01
    provides: [AutomationRun]
  - phase: 06-02
    provides: [AutomationTaskResult]
provides:
  - Structured report context builder
  - Canonical Markdown daily report
  - Calendar-yesterday window handling
affects: [operator-reporting, automation-output]
tech-stack:
  added: []
  patterns: [markdown-first, structured-query-reporting]
key-files:
  created:
    - src/polymarket_quant/services/report_builder.py
    - src/polymarket_quant/services/report_templates.py
    - src/polymarket_quant/testsupport.py
    - tests/unit/test_report_builder.py
key-decisions:
  - "Markdown is the canonical Phase 6 report artifact."
  - "Daily window semantics use calendar yesterday, not rolling 24 hours."
patterns-established:
  - "Reports summarize structured task results and operator queries rather than scraping logs."
requirements-completed: [AUTO-02, AUTO-03]
duration: 0 min
completed: 2026-04-22
---

# Phase 6 Plan 03: Report Builder Summary

**Structured daily report context and canonical Markdown output**

## Accomplishments

- Added `ReportBuilder` to assemble operator query data, task outcomes, and window metadata into one report context.
- Added a Markdown report renderer with the locked sections: overview, sync, health, strategy summary, pnl/exposure, alerts, and runs/artifacts.
- Implemented calendar-yesterday window calculation with timezone-aware boundaries.
- Added tests for failed/skipped task visibility and required report sections.

## Task Commits

1. **Tasks 1-2: Report context and Markdown rendering** - pending phase commit

## Deviations from Plan

- None.

## Self-Check: PASSED

- `pytest tests/unit/test_report_builder.py -q` -> 4 passed.
- Required sections and unhealthy-task visibility are present in Markdown output.

---
*Phase: 06-automation-scheduled-reports*
*Completed: 2026-04-22*
