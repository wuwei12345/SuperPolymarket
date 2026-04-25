# Polymarket Quant Simulator

Simulation-first Polymarket research system for building a canonical market universe, market data substrate, replay workflows, and paper execution.

中文新手文档：

- [docs/新手使用说明与测试用例.md](docs/新手使用说明与测试用例.md)

## Phase 1 Market Universe UI

Run the Phase 1 browser page:

```bash
streamlit run src/polymarket_quant/ui/market_universe_app.py
```

Each Streamlit page now includes a `Language / 语言` selector in the sidebar for English and Chinese UI copy.

Phase 1 defaults to `active + accepting orders` markets. The page uses left filters, a right-side table, and a bottom collapsible timeline so the sync process and market rows can be checked together.

The table includes source labels for Gamma/CLOB provenance. Gamma supplies human-readable market metadata such as question, category, liquidity, and end date; CLOB supplies condition and Yes/No token mappings through normalization.

## Phase 2 Market Data Store

Phase 2 stores market data in PostgreSQL. Set `DATABASE_URL` before running live ingestion commands, for example:

```bash
export DATABASE_URL=postgresql://localhost/polymarket_quant
```

Phase 1 SQLite MarketStore remains the market universe source; Phase 2 imports reference tokens into PostgreSQL. The Phase 2 store uses separate PostgreSQL schemas for reference data, raw payloads, normalized market data, and query views.

## Phase 2 REST Backfill

REST backfill selects top active + accepting tokens from the Phase 1 universe and writes CLOB price history plus current book snapshots into PostgreSQL.

Required environment:

```bash
export DATABASE_URL=postgresql://localhost/polymarket_quant
export POLYMARKET_TOP_N=50
```

Run:

```bash
python -m polymarket_quant.services.backfill
```

`POLYMARKET_TOP_N=50` is the default. The command expects Phase 1 market data in `data/markets.sqlite3`.

## Phase 2 Realtime Collector

The realtime collector subscribes to the Polymarket market WebSocket for top-N token IDs and writes raw events before normalized latest-state rows.

Required environment:

```bash
export DATABASE_URL=postgresql://localhost/polymarket_quant
export POLYMARKET_TOP_N=50
```

Run:

```bash
python -m polymarket_quant.services.realtime_collector
```

On reconnect, the collector records a gap interval and repairs the window with a REST snapshot plus recent price history marked as gap-filled data.

## Phase 2 Market Data Monitor

Run the Phase 2 browser page:

```bash
streamlit run src/polymarket_quant/ui/market_data_app.py
```

The page shows latest bid/ask, spread, midpoint, last trade, recent price curve, source, and gap-fill markers.

Final smoke checks:

```bash
pytest -q
python -m polymarket_quant.services.backfill
python -m polymarket_quant.services.realtime_collector
```

Live commands require `DATABASE_URL`, Phase 1 market universe data, and public API connectivity.

## Phase 3 Paper Exchange

Phase 3 provides a simulation-only paper exchange boundary for `OrderIntent` submissions. It supports limit orders, marketable limit orders, cancel/replace, `client_order_id`, depth-driven paper fills, partial fills, tick-size and minimum-size checks, submit/cancel latency, cash/position/fill/fee ledger entries, conservative mark valuation, realized/unrealized PnL, and structured `RiskDecision` output.

Phase 3 does not place live orders or use wallet authentication.

### Deferred beyond P0

- GTD expiry
- post_only enforcement
- portfolio-level hard risk
- reward estimate
- market/FOK/FAK orders
- builder fees
- high-fidelity tick-by-tick replay fills

## Phase 4 Strategy Runtime

Phase 4 turns the simulator into a reproducible research runtime. The goal is not merely to run strategy code, but to produce explainable runs that can be replayed, compared, and audited.

Strategies are Python classes with a stable lifecycle:

```python
class Strategy:
    def on_init(self, ctx): ...
    def on_event(self, event, ctx): ...
    def on_clock(self, ts, ctx): ...
    def on_finish(self, ctx): ...
```

Strategies emit target-based `Signal` objects such as `target_exposure` or `target_position`. A separate sizing and execution adapter translates those signals into `OrderIntent`, and realtime paper mode routes them through `PaperExchangeService`.

Phase 4 supports three run modes from one config surface:

- `replay`
- `research`
- `realtime paper`

Primary entry point:

```python
from polymarket_quant.services import StrategyCliService

cli = StrategyCliService("data/runs")
result = cli.run(strategy, "config/phase4.yaml", events=events)
```

Config files can be YAML or JSON. The CLI resolves defaults before execution and persists the effective configuration into `manifest.json`.

Each run writes a stable artifact directory keyed by `run_id`, including:

- `manifest.json`
- `signals.parquet`
- `order_intents.parquet`
- `orders.parquet`
- `fills.parquet`
- `positions.parquet`
- `risk_decisions.parquet`
- `strategy.log`
- `framework.log`

Run summaries are computed from factual artifacts, not log scraping. Phase 4 metrics include total return, realized/unrealized PnL, turnover, fill rate, cancel rate, average holding time, max drawdown, exposure peak, reject count, and slippage metrics.

## Simulation Result Dashboard

Run the browser page:

```bash
streamlit run src/polymarket_quant/ui/operator_console_app.py
```

The first screen is now result-first. It reads `data/runtime/latest_snapshot.json` when available, then falls back to strategy artifacts under `data/runs`.

Default dashboard sections:

- total PnL, today PnL, realized/unrealized PnL
- current exposure, max drawdown, positions, open orders
- PnL/Equity, Drawdown, and Exposure curves
- current simulation positions
- recent simulated trades
- risk and alert summary

Technical operator views are still available from the page selector:

- `Run Details`: strategy overview, positions/orders, PnL/exposure, artifacts
- `System Health`: connection state and guarded mode switch
- `Debug`: full alert timeline and low-level troubleshooting

Mode changes are guarded. The console requires a `preflight` step first, shows blocking and warning reasons, and only applies the switch after explicit `confirm` input.

`live-disabled` remains a protective boundary in v1. It is not a live-trading mode, and Phase 5 does not enable wallet auth or real order submission.

## Phase 6 Automation + Scheduled Reports

Phase 6 adds a one-shot automation workflow for the default daily operator loop:

- market sync
- realtime health check
- strategy batch run
- report generation

Primary config:

- [config/automation.daily.yaml](/Users/wuwei/Documents/polymarketQuantification/config/automation.daily.yaml)
- [config/strategy.daily.yaml](/Users/wuwei/Documents/polymarketQuantification/config/strategy.daily.yaml)

Run it manually:

```bash
python -m polymarket_quant.services.automation_cli config/automation.daily.yaml
```

The automation run writes:

- strategy artifacts under `data/runs`
- automation manifests under `data/automation`
- daily Markdown and HTML reports under `data/reports/daily`

The default report window is `昨日自然日`. Markdown is the canonical report output; HTML is generated from the same content.

Example `cron` entry:

```cron
15 8 * * * cd /Users/wuwei/Documents/polymarketQuantification && python -m polymarket_quant.services.automation_cli config/automation.daily.yaml >> data/automation/cron.log 2>&1
```

This keeps scheduling outside the application. Phase 6 still runs strategies in `realtime_paper` mode only.

### Optional Background Daemon

The one-shot CLI and cron flow remains supported. For a more continuous local simulation experience, run the lightweight daemon:

```bash
python -m polymarket_quant.services.background_daemon --config config/daemon.local.yaml
```

Run one due cycle and exit:

```bash
python -m polymarket_quant.services.background_daemon --config config/daemon.local.yaml --once
```

Request a graceful stop:

```bash
python -m polymarket_quant.services.background_daemon --config config/daemon.local.yaml --stop
```

Daemon runtime files:

- `data/runtime/daemon_state.json`: heartbeat, current task, last/next execution time, latest error, latest run/report pointers
- `data/runtime/latest_snapshot.json`: dashboard-ready simulation result snapshot
- `data/runtime/daemon_state.lock`: single-instance lock
- `data/runtime/stop.flag`: graceful stop flag

Schedule config:

- [config/daemon.local.yaml](/Users/wuwei/Documents/polymarketQuantification/config/daemon.local.yaml)
