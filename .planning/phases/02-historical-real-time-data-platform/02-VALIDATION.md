---
phase: 02
slug: historical-real-time-data-platform
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-18
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/unit -q` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~35 seconds without live PostgreSQL |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit -q`
- **After every plan wave:** Run `pytest -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds for unit suite; PostgreSQL live smoke is manual/env-gated

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | DATA-01/DATA-03 | T-02-01 | PostgreSQL schema separates reference/raw/normalized/views | unit | `pytest tests/unit/test_market_data_store.py -q` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | DATA-01/DATA-03 | T-02-02 | Raw payload JSONB and normalized rows retain source/gap fields | unit | `pytest tests/unit/test_market_data_store.py -q` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | DATA-01/DATA-04 | T-02-03 | REST backfill chunks price history at 20 tokens and writes raw before normalized | unit | `pytest tests/unit/test_backfill.py -q` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | DATA-01 | T-02-04 | Current book snapshots produce best bid/ask, spread, midpoint, and last trade | unit | `pytest tests/unit/test_backfill.py -q` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 3 | DATA-02/DATA-03 | T-02-05 | WS subscription uses token IDs and persists raw events first | unit | `pytest tests/unit/test_realtime_collector.py -q` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 3 | DATA-02/DATA-03 | T-02-06 | Reconnect creates gap interval and invokes REST snapshot plus recent history repair | unit | `pytest tests/unit/test_realtime_collector.py -q` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 4 | DATA-01/DATA-03 | T-02-07 | Query layer exposes latest BBO/spread/last trade/price series with source and gap markers | unit | `pytest tests/unit/test_market_data_queries.py -q` | ❌ W0 | ⬜ pending |
| 02-04-02 | 04 | 4 | DATA-01/DATA-03 | — | Streamlit inspection surface contains required fields and no trading/PnL controls | unit | `pytest tests/unit/test_market_data_ui_contract.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — declares `psycopg[binary]` and `websockets`
- [ ] `tests/unit/test_market_data_store.py` — schema and repository behavior tests
- [ ] `tests/unit/test_backfill.py` — REST adapter/backfill chunking and normalization tests
- [ ] `tests/unit/test_realtime_collector.py` — fake WebSocket, raw persistence, reconnect, and gap-fill tests
- [ ] `tests/unit/test_market_data_queries.py` — latest-state and price-series query transform tests
- [ ] `tests/unit/test_market_data_ui_contract.py` — inspection page contract tests

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PostgreSQL live schema smoke | DATA-01/DATA-03 | Local PostgreSQL availability is environment-dependent | Set `DATABASE_URL`, run schema init/backfill smoke against a disposable database, verify schemas `reference`, `raw`, `normalized`, and `views` exist |
| Live public Polymarket data smoke | DATA-01/DATA-02 | Live data availability and rate limits should not make unit tests flaky | Run top-N selection, REST backfill for a small `POLYMARKET_TOP_N=4`, then run WS collector for 30 seconds and inspect timeline/log rows |
| Browser inspection layout | DATA-01/DATA-03 | Streamlit visual layout is best checked in a browser | Run `streamlit run src/polymarket_quant/ui/market_data_app.py`, verify latest bid/ask, spread, last trade, price curve, source, and gap-fill markers |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 45s for unit suite
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-18
