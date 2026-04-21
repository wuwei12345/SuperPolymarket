---
phase: 04
slug: strategy-research-workbench
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-21
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/unit/test_strategy_models.py tests/unit/test_run_artifacts.py tests/unit/test_replay_runtime.py tests/unit/test_signal_execution.py tests/unit/test_strategy_cli.py -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run the relevant plan-specific pytest command.
- **After every plan wave:** Run `pytest -q`.
- **Before `$gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 10 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | STRAT-01, STRAT-03 | T-04-01 | Strategy class contract is typed, explicit, and shared across modes | unit | `pytest tests/unit/test_strategy_models.py -q` | W0 | pending |
| 04-02-01 | 02 | 2 | OPS-02 | T-04-02 | Run bundles persist manifest, resolved config, artifacts, and logs without silent omission | unit | `pytest tests/unit/test_run_artifacts.py -q` | W0 | pending |
| 04-03-01 | 03 | 3 | STRAT-01, STRAT-02 | T-04-03 | Replay runtime consumes events and clock ticks without future-data leakage | unit | `pytest tests/unit/test_replay_runtime.py -q` | W0 | pending |
| 04-04-01 | 04 | 4 | STRAT-02, STRAT-03 | T-04-04 | Target-based signals translate through sizing/execution into `PaperExchangeService` without direct order emission from strategies | unit | `pytest tests/unit/test_signal_execution.py -q` | W0 | pending |
| 04-05-01 | 05 | 5 | OPS-02, STRAT-02 | T-04-05 | CLI resolves config, creates run directories, and emits comparable metrics/output summaries | unit | `pytest tests/unit/test_strategy_cli.py -q` | W0 | pending |

---

## Wave 0 Requirements

- [x] Existing pytest infrastructure already exists in `pyproject.toml`
- [ ] `tests/unit/test_strategy_models.py` — strategy contract and signal schema tests
- [ ] `tests/unit/test_run_artifacts.py` — manifest and bundle writer tests
- [ ] `tests/unit/test_replay_runtime.py` — replay/event/clock loop tests
- [ ] `tests/unit/test_signal_execution.py` — target-to-order translation and paper execution tests
- [ ] `tests/unit/test_strategy_cli.py` — config resolution and CLI smoke tests
- [ ] `pyarrow`, `duckdb`, and `PyYAML` dependency additions if implementation chooses them

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Short end-to-end replay run produces a readable artifact directory | OPS-02 | Human review of artifact readability is faster than snapshot-heavy automated assertions | Run one small replay config, inspect `manifest.json`, parquet file names, and logs in the generated run directory |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify.
- [x] Wave 0 covers all missing references.
- [x] No watch-mode flags.
- [x] Feedback latency < 10 seconds.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-04-21
