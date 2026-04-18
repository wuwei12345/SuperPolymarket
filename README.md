# Polymarket Quant Simulator

Simulation-first Polymarket research system for building a canonical market universe, market data substrate, replay workflows, and paper execution.

## Phase 1 Market Universe UI

Run the Phase 1 browser page:

```bash
streamlit run src/polymarket_quant/ui/market_universe_app.py
```

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
