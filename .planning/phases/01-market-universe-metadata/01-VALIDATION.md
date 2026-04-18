---
phase: 01
slug: market-universe-metadata
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-18
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/unit -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit -q`
- **After every plan wave:** Run `pytest -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | MKT-01/MKT-03 | T-01-01 | Reject malformed market IDs instead of treating them as valid | unit | `pytest tests/unit/test_market_models.py -q` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | MKT-01/MKT-03 | T-01-01 | Persist canonical fields and source labels without loss | unit | `pytest tests/unit/test_market_store.py -q` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 2 | MKT-01/MKT-03 | T-01-02 | Bound retries and expose retry failures to logs | unit | `pytest tests/unit/test_market_sync.py -q` | ❌ W0 | ⬜ pending |
| 01-02-02 | 02 | 2 | MKT-01/MKT-03 | T-01-01 | Only active + accepting markets become valid universe rows | unit | `pytest tests/unit/test_market_sync.py -q` | ❌ W0 | ⬜ pending |
| 01-03-01 | 03 | 3 | MKT-02/MKT-03 | — | UI exposes required filters, columns, and source labels | unit | `pytest tests/unit/test_market_universe_ui_contract.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — declares pytest configuration and Phase 1 dependencies
- [ ] `tests/unit/test_market_models.py` — stubs for canonical model and ID mapping behavior
- [ ] `tests/unit/test_market_store.py` — stubs for local persistence behavior
- [ ] `tests/unit/test_market_sync.py` — stubs for API sync, retry timeline, and active+accepting filtering
- [ ] `tests/unit/test_market_universe_ui_contract.py` — stubs for UI contract constants and copy

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Browser visual layout | MKT-02/MKT-03 | Streamlit layout fidelity is easier to inspect visually in Phase 1 | Run the app, trigger sync with mocked or live data, verify left filters, right table, bottom collapsible timeline |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-18
