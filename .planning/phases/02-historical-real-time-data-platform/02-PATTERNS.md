# Phase 02 — Pattern Map

**Created:** 2026-04-18
**Status:** Complete

## Purpose

Map the Phase 2 files to existing local patterns so execution extends the codebase instead of inventing a new shape.

## Existing Patterns To Reuse

| New file / area | Closest existing analog | Pattern to copy |
|-----------------|-------------------------|-----------------|
| `src/polymarket_quant/domain/market_data.py` | `src/polymarket_quant/domain/market.py` | Pydantic models with strict extra handling, clear identifier fields, simple validators |
| `src/polymarket_quant/adapters/polymarket.py` extensions | `src/polymarket_quant/adapters/polymarket.py` | Small injectable `httpx.Client`, module constants for base URLs, explicit methods, `response.raise_for_status()` |
| `src/polymarket_quant/storage/market_data_store.py` | `src/polymarket_quant/storage/market_store.py` | Repository object with `init_schema()` and typed conversion helpers, but backed by PostgreSQL `psycopg` |
| `src/polymarket_quant/services/universe_selector.py` | `src/polymarket_quant/services/market_sync.py` | Service class/function boundaries, dataclasses for results/events, deterministic pure helpers |
| `src/polymarket_quant/services/backfill.py` | `src/polymarket_quant/services/market_sync.py` | Timeline events, retryable orchestration, testable injected clients/stores |
| `src/polymarket_quant/adapters/polymarket_ws.py` | New async analog | Keep adapter thin and injectable; do not mix persistence into the socket adapter |
| `src/polymarket_quant/services/realtime_collector.py` | `src/polymarket_quant/services/market_sync.py` | Orchestrator service with explicit result/event dataclasses and no UI dependencies |
| `src/polymarket_quant/services/market_data_queries.py` | `src/polymarket_quant/ui/market_universe_app.py` data helpers | Build dataframes/query DTOs in helpers that can be unit-tested without rendering Streamlit |
| `src/polymarket_quant/ui/market_data_app.py` | `src/polymarket_quant/ui/market_universe_app.py` | Streamlit-style `main()`, helper functions, table-first internal tool, no trading controls |

## Concrete Code Patterns

### HTTP adapter pattern

Existing pattern:

```python
class ClobClient:
    def __init__(
        self,
        client: httpx.Client | None = None,
        base_url: str = CLOB_BASE_URL,
    ) -> None:
        self.client = client or httpx.Client()
        self.base_url = base_url.rstrip("/")
```

Phase 2 should extend this class rather than adding a second REST client. New methods should accept concrete parameters and return JSON payloads:

- `fetch_prices_history_batch(markets: list[str], start_ts: int | None, end_ts: int | None, interval: str = "1d", fidelity: int = 1) -> dict[str, Any]`
- `fetch_order_books(token_ids: list[str]) -> list[dict[str, Any]]`
- `fetch_market_prices(params: list[dict[str, str]]) -> dict[str, dict[str, float]]`
- `fetch_last_trade_prices(token_ids: list[str]) -> list[dict[str, Any]]`

### Store pattern

Existing pattern:

```python
class MarketStore:
    def init_schema(self) -> None:
        ...

    def upsert_markets(self, markets: Sequence[CanonicalMarket]) -> int:
        ...
```

Phase 2 should keep the explicit repository style:

- `MarketDataStore.init_schema()`
- `MarketDataStore.upsert_reference_tokens(tokens)`
- `MarketDataStore.insert_raw_rest_payload(...)`
- `MarketDataStore.insert_raw_ws_event(...)`
- `MarketDataStore.upsert_price_history_points(...)`
- `MarketDataStore.insert_book_snapshot(...)`
- `MarketDataStore.upsert_best_bid_ask(...)`
- `MarketDataStore.upsert_last_trade(...)`
- `MarketDataStore.record_gap_interval(...)`
- `MarketDataStore.fetch_latest_state(limit)`
- `MarketDataStore.fetch_price_series(token_id, start_ts, end_ts)`

### Event/timeline pattern

Existing `SyncEvent` fields:

- `timestamp`
- `step`
- `source`
- `status`
- `message`

Phase 2 should reuse this shape for backfill and realtime events, adding only optional machine keys when needed:

- `token_id`
- `condition_id`
- `collection_run_id`
- `gap_fill`

### UI pattern

Phase 1 UI already uses contract constants and tests. Phase 2 should add a separate contract section in `src/polymarket_quant/ui/contracts.py`:

- `MARKET_DATA_PAGE_TITLE = "Market Data Monitor"`
- `MARKET_DATA_COLUMNS = ["question", "token_id", "outcome", "best_bid", "best_ask", "spread", "midpoint", "last_trade_price", "source", "gap_fill"]`
- `MARKET_DATA_REQUIRED_SECTIONS = ["latest table", "price curve", "timeline log"]`

## Anti-Patterns To Avoid

- Do not replace Phase 1 SQLite `MarketStore` with PostgreSQL in a way that breaks the already verified market universe UI.
- Do not store only normalized rows. Raw REST and WS payloads are mandatory.
- Do not subscribe to market WS by `condition_id`; use token IDs in `assets_ids`.
- Do not hide gap-filled rows behind the same source labels as uninterrupted live data.
- Do not add strategy, paper order, position, PnL, wallet/auth, or real trading controls.

## PATTERN MAPPING COMPLETE
