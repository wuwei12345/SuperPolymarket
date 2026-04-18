# AGENTS

This repository uses GSD planning artifacts as the source of truth for implementation work.

## Read First

Before planning or coding, read these files in order:

1. `.planning/PROJECT.md`
2. `.planning/REQUIREMENTS.md`
3. `.planning/ROADMAP.md`
4. `.planning/STATE.md`
5. `.planning/research/SUMMARY.md`

## Project Guardrails

- This project is **Polymarket-only** in v1.
- Prefer **official Polymarket APIs and official SDKs** over hand-rolled protocol logic.
- v1 is **simulation-first**. Do not introduce real-money order flow unless a later requirement explicitly changes scope.
- Treat `market_id`, `condition_id`, and `token_id` as separate identifiers with explicit mappings.
- Historical fidelity matters. If a change touches backtests or execution quality, preserve raw WebSocket event capture and replay semantics.
- Any future live-trading work must include geoblock, auth, funder, and allowance checks before order submission.

## Current Focus

Active milestone starts at:

- **Phase 1: Market Universe & Metadata**

Preferred next command:

- `$gsd-discuss-phase 1`
