---
phase: 03
slug: simulation-exchange-portfolio-ledger
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-19
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/unit/test_simulation_models.py tests/unit/test_simulation_store.py tests/unit/test_order_risk.py tests/unit/test_fill_engine.py tests/unit/test_portfolio_ledger.py tests/unit/test_paper_exchange.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~1 second |

---

## Sampling Rate

- **After every task commit:** Run the relevant plan-specific pytest command.
- **After every plan wave:** Run `pytest -q`.
- **Before `$gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 5 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | SIM-01 | T-03-01 | Reject invalid identifiers and unsupported order semantics | unit | `pytest tests/unit/test_simulation_models.py -q` | W0 | pending |
| 03-01-02 | 01 | 1 | SIM-03 | T-03-02 | Persist immutable ledger facts separately from valuation snapshots | unit | `pytest tests/unit/test_simulation_store.py -q` | W0 | pending |
| 03-02-01 | 02 | 2 | SIM-01, RISK-01 | T-03-03 | Hard rejects for balance, size, tick, order, market, token constraints | unit | `pytest tests/unit/test_order_risk.py -q` | W0 | pending |
| 03-02-02 | 02 | 2 | SIM-01 | T-03-04 | Invalid lifecycle transitions cannot advance order state | unit | `pytest tests/unit/test_order_risk.py -q` | W0 | pending |
| 03-03-01 | 03 | 2 | SIM-02 | T-03-05 | Fill model cannot overfill available depth or ignore tick/min-size context | unit | `pytest tests/unit/test_fill_engine.py -q` | W0 | pending |
| 03-04-01 | 04 | 3 | SIM-03 | T-03-06 | Cash, position, fee, realized PnL, and unrealized PnL are tracked separately | unit | `pytest tests/unit/test_portfolio_ledger.py -q` | W0 | pending |
| 03-05-01 | 05 | 4 | SIM-01, SIM-02, SIM-03, RISK-01 | T-03-07 | End-to-end paper exchange records risk decisions before order acceptance | unit | `pytest tests/unit/test_paper_exchange.py -q` | W0 | pending |

---

## Wave 0 Requirements

Existing pytest infrastructure covers all Phase 3 requirements. Each plan creates its own tests before or alongside implementation.

---

## Manual-Only Verifications

All Phase 3 P0 behaviors have automated verification. Live PostgreSQL smoke can be done later with a disposable `DATABASE_URL`, but it is not required for P0 plan validation.

---

## Validation Sign-Off

- [x] All tasks have automated verify commands.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency < 5 seconds.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-04-19
