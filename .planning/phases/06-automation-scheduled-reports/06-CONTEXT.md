# Phase 6: Automation + Scheduled Reports - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 6 delivers the first automation and scheduled reporting layer for the simulator. It adds a standard CLI entrypoint, YAML-driven automation configuration, a lightweight runner suitable for cron-based scheduling, and recurring report generation from existing run artifacts and operator read models.

This phase builds on the completed runtime, artifacts, metrics, and operator query layers from Phases 4 and 5. It does not introduce real trading, internal long-running scheduler infrastructure, notification delivery systems, or automatic live-mode transitions.

</domain>

<decisions>
## Implementation Decisions

### Automation scope
- **D-01:** Phase 6 default automation chain must include only:
  - market sync
  - realtime health check
  - strategy batch run
  - report generation
- **D-02:** `backfill` must not be part of the default scheduled mainline.
- **D-03:** `backfill` remains available only as:
  - manual trigger
  - low-frequency补数任务

### Scheduling model
- **D-04:** Phase 6 must support both CLI invocation and cron-based external scheduling.
- **D-05:** The first implementation target is `CLI + cron` minimum viable automation, not a full internal scheduler.
- **D-06:** The project may include a lightweight runner/orchestrator, but it must not become a heavy built-in scheduling system in this phase.
- **D-07:** Scheduling responsibility remains with the host system scheduler or external orchestrator; README should document cron examples clearly.

### Report outputs
- **D-08:** Default report outputs are:
  - `Markdown`
  - `HTML`
- **D-09:** CSV summary output is deferred and not part of the first-class Phase 6 artifact set.
- **D-10:** Reports are written to disk as files, not pushed to external channels in this phase.

### Strategy automation policy
- **D-11:** Automated strategy runs must come from a YAML-declared strategy list, not from hardcoded strategy selection and not from a single “latest strategy” shortcut.
- **D-12:** Phase 6 default automated run mode is `realtime_paper`.
- **D-13:** `replay` and `research` remain supported, but only for manual or专项批任务 workflows, not as the default scheduled automation mode.

### Reporting cadence and window semantics
- **D-14:** The system should be able to support both daily reports and more frequent health-style reporting in the future.
- **D-15:** Phase 6 first-class recurring report is a `daily report`.
- **D-16:** The default daily report window is `昨日自然日`, not “today” and not “last 24 hours”.

### Failure handling
- **D-17:** Failure handling follows a graded policy, not pure fail-fast and not pure best-effort.
- **D-18:** If market sync or realtime health check fails, automation continues, but the report must mark the failure clearly.
- **D-19:** If prerequisites for strategy execution are not met, the system must skip strategy execution rather than forcing a broken run.
- **D-20:** Report generation must always be attempted, even when earlier steps fail.

### Report content
- **D-21:** The default daily report must include all of the following sections:
  - run overview
  - market sync summary
  - realtime health summary
  - strategy run summary
  - pnl / drawdown / exposure
  - `Critical` / `Warning` alert summary
  - runs / artifacts index

### Configuration and entrypoints
- **D-22:** Phase 6 primary invocation is a `CLI` entrypoint.
- **D-23:** Phase 6 primary configuration format is `YAML`.
- **D-24:** README must include cron examples for scheduled execution.
- **D-25:** A single automation config should declare:
  - enabled tasks
  - strategy list
  - artifact root
  - report output directory
  - report mode/output settings
  - time-window policy

### the agent's Discretion
- Exact CLI command names and flag names
- Exact report directory layout and filename conventions
- Exact HTML rendering approach, provided Markdown remains the canonical first output
- Exact structure of health-check substeps
- Exact retry policy per task, provided the locked graded-failure semantics remain intact

</decisions>

<specifics>
## Specific Ideas

- The user explicitly does not want “全自动全都跑”; Phase 6 should automate the stable daily operator workflow, not every possible maintenance job.
- `backfill` is intentionally treated as a sidecar operation rather than part of the default recurring chain.
- The desired operating model is pragmatic: the project should provide a standard CLI and a lightweight runner, while cron or another external scheduler remains the primary way to run jobs on a schedule.
- Reports should be readable by humans first, which is why `Markdown + HTML` is preferred over CSV-first output.
- Strategy automation should be driven from configuration so the user can change the scheduled strategy set without editing code.
- Daily reporting must align with a calendar day boundary (`昨日自然日`) rather than a rolling 24-hour window.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project and requirement constraints
- `.planning/PROJECT.md` — simulation-first, Polymarket-only, and no-live-trading-v1 constraints
- `.planning/REQUIREMENTS.md` — existing reproducibility, operator, and reporting-adjacent requirements that Phase 6 must extend rather than contradict
- `.planning/ROADMAP.md` — existing phase boundaries and current milestone shape; note that Phase 6 is not yet formally inserted
- `.planning/STATE.md` — current phase-state file is stale, but still documents system-level risks and context

### Prior phase decisions that constrain Phase 6
- `.planning/phases/04-strategy-research-workbench/04-CONTEXT.md` — run modes, manifest/artifact bundle contract, and reproducibility decisions
- `.planning/phases/05-operator-console-safety-controls/05-CONTEXT.md` — operator-facing aggregation, alert semantics, and mode/preflight boundaries

### Existing implementation references
- `src/polymarket_quant/services/strategy_cli.py` — standard strategy execution entry surface and run-artifact creation
- `src/polymarket_quant/services/run_artifacts.py` — manifest/log/parquet bundle writer
- `src/polymarket_quant/services/operator_queries.py` — unified read model for operator summaries, runs, artifacts, and alert timeline
- `src/polymarket_quant/services/operator_safety.py` — alert/block/preflight semantics that reports may need to summarize
- `src/polymarket_quant/services/market_sync.py` — market sync task entry and timeline event model
- `src/polymarket_quant/services/realtime_collector.py` — realtime collector and reconnect/gap-fill behavior
- `README.md` — current public run commands and operator-console framing

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `StrategyCliService` already provides the main execution boundary for running configured strategies and writing manifest-driven artifact bundles.
- `RunArtifactBundleWriter` already persists the structured outputs that Phase 6 reports should read instead of scraping logs.
- `OperatorQueryService` already exposes grouped summaries, detail panes, alert timeline data, and runs/artifacts indices that can feed reports directly.
- `OperatorSafetyService` and the operator runtime registry provide structured alert and status signals that can be summarized in health reports.
- `market_sync.py` already has a step/timeline model that can support reportable sync outcomes.

### Established Patterns
- The project prefers explicit typed services and structured artifacts over ad hoc scripts.
- YAML/JSON config and CLI invocation are already the dominant operational patterns.
- Existing observability work favors human-readable summaries plus factual artifact linkage.
- Mode boundaries and live-disabled protections are already explicit and should not be weakened by automation.

### Integration Points
- Phase 6 should orchestrate existing services rather than duplicating execution paths.
- Report generation should read:
  - run manifests
  - parquet artifacts
  - operator query outputs
  - health-check results captured during the automation run
- Automation outputs should themselves be traceable, likely via an automation-run manifest or equivalent structured result object.
- Cron examples in README should invoke the same CLI entrypoint used for manual one-shot runs.

</code_context>

<deferred>
## Deferred Ideas

- Email / Feishu / Telegram / webhook delivery
- Full internal scheduler or daemonized scheduling subsystem
- CSV-first reporting outputs
- Automatic mode switching or unattended operator approvals
- Including `backfill` in the default scheduled mainline
- Default scheduled `replay` or `research` batch jobs

</deferred>

---
*Phase: 06-automation-scheduled-reports*
*Context gathered: 2026-04-22*
