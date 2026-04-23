---
phase: 06
slug: automation-scheduled-reports
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-22
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/unit/test_automation_models.py tests/unit/test_automation_runner.py tests/unit/test_report_builder.py tests/unit/test_report_index.py tests/unit/test_automation_cli.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~4 seconds |

---

## Sampling Rate

- **After every task commit:** Run the relevant plan-specific pytest command.
- **After every plan wave:** Run `pytest -q`.
- **Before `$gsd-verify-work 6`:** Full suite must be green.
- **Max feedback latency:** 10 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | AUTO-01, AUTO-03 | T-06-01 | Automation run identity, resolved config, and task results are explicit and serializable | unit | `pytest tests/unit/test_automation_models.py -q` | W0 | pending |
| 06-02-01 | 02 | 2 | AUTO-01, AUTO-03 | T-06-02 | Runner follows graded failure semantics and still attempts report generation | unit | `pytest tests/unit/test_automation_runner.py -q` | W0 | pending |
| 06-03-01 | 03 | 3 | AUTO-02, AUTO-03 | T-06-03 | Report builder produces truthful Markdown sections from structured artifacts and operator queries | unit | `pytest tests/unit/test_report_builder.py -q` | W0 | pending |
| 06-04-01 | 04 | 4 | AUTO-02, AUTO-03 | T-06-04 | HTML export and report index preserve canonical content and stable file references | unit | `pytest tests/unit/test_report_index.py -q` | W0 | pending |
| 06-05-01 | 05 | 5 | AUTO-01, AUTO-02 | T-06-05 | CLI resolves YAML config, produces automation outputs, and docs reflect cron usage without implying an internal scheduler | unit | `pytest tests/unit/test_automation_cli.py -q` | W0 | pending |

---

## Wave 0 Requirements

- [x] Existing pytest infrastructure already exists in `pyproject.toml`
- [ ] `tests/unit/test_automation_models.py` — automation domain/config/result tests
- [ ] `tests/unit/test_automation_runner.py` — task orchestration and graded failure tests
- [ ] `tests/unit/test_report_builder.py` — Markdown report content tests
- [ ] `tests/unit/test_report_index.py` — HTML/index/output path tests
- [ ] `tests/unit/test_automation_cli.py` — CLI/config/docs integration tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cron example is understandable to a non-expert operator | AUTO-01 | Human readability and environment assumptions are easier to judge than unit-test snapshots | Read the README cron example and confirm the schedule, config path, and output location are obvious |
| Daily report reads like an operator summary rather than a raw dump | AUTO-02 | Information hierarchy is better judged by inspection than by string-only assertions | Generate a sample report and confirm overview, alerts, and artifacts are easy to scan in order |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency < 10 seconds.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-04-22
