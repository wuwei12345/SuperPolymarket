---
phase: 05
slug: operator-console-safety-controls
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-22
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/unit/test_operator_models.py tests/unit/test_operator_safety.py tests/unit/test_operator_queries.py tests/unit/test_operator_console_ui_contract.py tests/unit/test_operator_console.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~3 seconds |

---

## Sampling Rate

- **After every task commit:** Run the relevant plan-specific pytest command.
- **After every plan wave:** Run `pytest -q`.
- **Before `$gsd-verify-work 5`:** Full suite must be green.
- **Max feedback latency:** 10 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | OPS-01, OPS-03 | T-05-01 | Runtime state and heartbeats are explicit, not inferred from stale artifacts | unit | `pytest tests/unit/test_operator_models.py -q` | W0 | pending |
| 05-02-01 | 02 | 2 | RISK-02, OPS-03 | T-05-02 | Expiry, liquidity, connection, and mode rules yield conservative alert/block decisions and preflight blockers | unit | `pytest tests/unit/test_operator_safety.py -q` | W0 | pending |
| 05-03-01 | 03 | 3 | OPS-01, RISK-03 | T-05-03 | Operator queries merge run state, metrics, positions, orders, alerts, and grouped analytics consistently | unit | `pytest tests/unit/test_operator_queries.py -q` | W0 | pending |
| 05-04-01 | 04 | 4 | OPS-01 | T-05-04 | Console UI preserves the locked single-page layout, shared filters, strategy-first overview, and read-only event timeline | unit | `pytest tests/unit/test_operator_console_ui_contract.py -q` | W0 | pending |
| 05-05-01 | 05 | 5 | OPS-03, RISK-02 | T-05-05 | Mode switching requires preflight plus confirmation, and docs reflect the no-live-trading boundary | unit | `pytest tests/unit/test_operator_console.py -q` | W0 | pending |

---

## Wave 0 Requirements

- [x] Existing pytest infrastructure already exists in `pyproject.toml`
- [ ] `tests/unit/test_operator_models.py` — operator domain and heartbeat registry tests
- [ ] `tests/unit/test_operator_safety.py` — expiry/liquidity/block/preflight tests
- [ ] `tests/unit/test_operator_queries.py` — grouped operator view/query tests
- [ ] `tests/unit/test_operator_console_ui_contract.py` — UI contract/layout tests
- [ ] `tests/unit/test_operator_console.py` — end-to-end console/service/doc tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Homepage reads like a control console rather than a notebook/tabset | OPS-01 | Visual information hierarchy is easier to evaluate by inspection than snapshot-heavy unit tests | Run the Streamlit app, confirm the top status band answers “is anything broken or dangerous?” before the detailed panes |
| Mode switch UX shows preflight then explicit confirmation | OPS-03 | Human confirmation sequencing is clearer to assess interactively | Trigger a mode-change action in the UI and verify the preflight summary appears before any confirm control |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency < 10 seconds.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-04-22
