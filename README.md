# Polymarket Quant Simulator

Simulation-first Polymarket research system for building a canonical market universe, market data substrate, replay workflows, and paper execution.

## Phase 1 Market Universe UI

Run the Phase 1 browser page:

```bash
streamlit run src/polymarket_quant/ui/market_universe_app.py
```

Phase 1 defaults to `active + accepting orders` markets. The page uses left filters, a right-side table, and a bottom collapsible timeline so the sync process and market rows can be checked together.

The table includes source labels for Gamma/CLOB provenance. Gamma supplies human-readable market metadata such as question, category, liquidity, and end date; CLOB supplies condition and Yes/No token mappings through normalization.
