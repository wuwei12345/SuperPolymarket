CREATE SCHEMA IF NOT EXISTS reference;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS normalized;
CREATE SCHEMA IF NOT EXISTS views;
CREATE SCHEMA IF NOT EXISTS simulation;

CREATE TABLE IF NOT EXISTS reference.tokens (
    token_id TEXT PRIMARY KEY,
    condition_id TEXT,
    market_id TEXT,
    question TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('Yes', 'No')),
    category TEXT,
    liquidity NUMERIC,
    end_date TIMESTAMPTZ,
    active BOOLEAN NOT NULL DEFAULT true,
    accepting_orders BOOLEAN NOT NULL DEFAULT true,
    universe_rank INTEGER NOT NULL,
    selection_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reference.universe_runs (
    run_id TEXT PRIMARY KEY,
    selected_count INTEGER NOT NULL,
    selection_reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.rest_payloads (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    token_id TEXT,
    condition_id TEXT,
    payload JSONB NOT NULL,
    source_ts TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL,
    collection_run_id TEXT,
    connection_id TEXT,
    gap_fill BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS raw.websocket_events (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    token_id TEXT,
    condition_id TEXT,
    event_type TEXT,
    payload JSONB NOT NULL,
    source_ts TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL,
    collection_run_id TEXT,
    connection_id TEXT,
    gap_fill BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS raw.gap_fill_intervals (
    id BIGSERIAL PRIMARY KEY,
    token_ids TEXT[] NOT NULL,
    gap_started_at TIMESTAMPTZ NOT NULL,
    gap_ended_at TIMESTAMPTZ NOT NULL,
    connection_id TEXT,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS normalized.price_history (
    token_id TEXT NOT NULL,
    condition_id TEXT,
    price NUMERIC NOT NULL,
    source_ts TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    collection_run_id TEXT,
    gap_fill BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (token_id, source_ts, source, gap_fill)
);

CREATE TABLE IF NOT EXISTS normalized.book_snapshots (
    id BIGSERIAL PRIMARY KEY,
    token_id TEXT NOT NULL,
    condition_id TEXT,
    market TEXT,
    source_ts TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    book_hash TEXT,
    min_order_size NUMERIC,
    tick_size NUMERIC,
    neg_risk BOOLEAN,
    last_trade_price NUMERIC,
    collection_run_id TEXT,
    gap_fill BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS normalized.book_levels (
    snapshot_id BIGINT NOT NULL REFERENCES normalized.book_snapshots(id) ON DELETE CASCADE,
    token_id TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    price NUMERIC NOT NULL,
    size NUMERIC NOT NULL,
    level_index INTEGER NOT NULL,
    gap_fill BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (snapshot_id, side, level_index)
);

CREATE TABLE IF NOT EXISTS normalized.best_bid_ask (
    token_id TEXT PRIMARY KEY,
    condition_id TEXT,
    best_bid NUMERIC,
    best_ask NUMERIC,
    spread NUMERIC,
    midpoint NUMERIC,
    source_ts TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    collection_run_id TEXT,
    connection_id TEXT,
    gap_fill BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS normalized.last_trades (
    token_id TEXT PRIMARY KEY,
    condition_id TEXT,
    price NUMERIC NOT NULL,
    side TEXT,
    size NUMERIC,
    source_ts TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    collection_run_id TEXT,
    connection_id TEXT,
    gap_fill BOOLEAN NOT NULL DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_reference_tokens_condition_id
    ON reference.tokens (condition_id);
CREATE INDEX IF NOT EXISTS idx_reference_tokens_rank
    ON reference.tokens (universe_rank);
CREATE INDEX IF NOT EXISTS idx_raw_rest_token_received
    ON raw.rest_payloads (token_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_rest_condition_id
    ON raw.rest_payloads (condition_id);
CREATE INDEX IF NOT EXISTS idx_raw_rest_source_ts
    ON raw.rest_payloads (source_ts);
CREATE INDEX IF NOT EXISTS idx_raw_rest_gap_fill
    ON raw.rest_payloads (gap_fill);
CREATE INDEX IF NOT EXISTS idx_raw_ws_token_received
    ON raw.websocket_events (token_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_ws_condition_id
    ON raw.websocket_events (condition_id);
CREATE INDEX IF NOT EXISTS idx_raw_ws_source_ts
    ON raw.websocket_events (source_ts);
CREATE INDEX IF NOT EXISTS idx_raw_ws_gap_fill
    ON raw.websocket_events (gap_fill);
CREATE INDEX IF NOT EXISTS idx_price_history_token_ts
    ON normalized.price_history (token_id, source_ts DESC);
CREATE INDEX IF NOT EXISTS idx_price_history_condition_id
    ON normalized.price_history (condition_id);
CREATE INDEX IF NOT EXISTS idx_price_history_gap_fill
    ON normalized.price_history (gap_fill);
CREATE INDEX IF NOT EXISTS idx_book_snapshots_token_received
    ON normalized.book_snapshots (token_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_book_snapshots_condition_id
    ON normalized.book_snapshots (condition_id);
CREATE INDEX IF NOT EXISTS idx_book_snapshots_source_ts
    ON normalized.book_snapshots (source_ts);
CREATE INDEX IF NOT EXISTS idx_book_snapshots_gap_fill
    ON normalized.book_snapshots (gap_fill);
CREATE INDEX IF NOT EXISTS idx_best_bid_ask_received
    ON normalized.best_bid_ask (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_last_trades_received
    ON normalized.last_trades (received_at DESC);

CREATE OR REPLACE VIEW views.latest_market_state AS
SELECT
    t.question,
    t.token_id,
    t.outcome,
    t.condition_id,
    b.best_bid,
    b.best_ask,
    b.spread,
    b.midpoint,
    l.price AS last_trade_price,
    COALESCE(l.side, NULL) AS last_trade_side,
    COALESCE(b.source, l.source, 'Unknown') AS source,
    COALESCE(b.gap_fill, false) OR COALESCE(l.gap_fill, false) AS gap_fill,
    GREATEST(
        COALESCE(b.received_at, '-infinity'::timestamptz),
        COALESCE(l.received_at, '-infinity'::timestamptz)
    ) AS received_at
FROM reference.tokens t
LEFT JOIN normalized.best_bid_ask b ON b.token_id = t.token_id
LEFT JOIN normalized.last_trades l ON l.token_id = t.token_id;

CREATE OR REPLACE VIEW views.price_series_recent AS
SELECT
    p.token_id,
    t.question,
    t.outcome,
    p.price,
    p.source_ts,
    p.received_at,
    p.source,
    p.gap_fill
FROM normalized.price_history p
LEFT JOIN reference.tokens t ON t.token_id = p.token_id;

CREATE TABLE IF NOT EXISTS simulation.orders (
    client_order_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    token_id TEXT NOT NULL,
    condition_id TEXT,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type TEXT NOT NULL CHECK (order_type IN ('LIMIT')),
    price NUMERIC NOT NULL,
    size NUMERIC NOT NULL,
    remaining_size NUMERIC NOT NULL,
    status TEXT NOT NULL,
    time_in_force TEXT NOT NULL CHECK (time_in_force IN ('GTC', 'GTD')),
    post_only BOOLEAN NOT NULL DEFAULT false,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL,
    reject_reason TEXT
);

CREATE TABLE IF NOT EXISTS simulation.order_transitions (
    id BIGSERIAL PRIMARY KEY,
    client_order_id TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation.fills (
    fill_id TEXT PRIMARY KEY,
    client_order_id TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    token_id TEXT NOT NULL,
    condition_id TEXT,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    price NUMERIC NOT NULL,
    size NUMERIC NOT NULL,
    fee NUMERIC NOT NULL DEFAULT 0,
    liquidity_role TEXT NOT NULL CHECK (liquidity_role IN ('MAKER', 'TAKER')),
    source_snapshot_id BIGINT,
    source_ts TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation.cash_ledger (
    entry_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    client_order_id TEXT,
    fill_id TEXT,
    delta NUMERIC NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation.position_ledger (
    entry_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    token_id TEXT NOT NULL,
    condition_id TEXT,
    client_order_id TEXT,
    fill_id TEXT,
    delta NUMERIC NOT NULL,
    price NUMERIC NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation.risk_decisions (
    id BIGSERIAL PRIMARY KEY,
    decision TEXT NOT NULL CHECK (decision IN ('ALLOW', 'WARN', 'REJECT')),
    client_order_id TEXT NOT NULL,
    token_id TEXT NOT NULL,
    condition_id TEXT,
    checks JSONB NOT NULL,
    reasons TEXT[] NOT NULL,
    warnings TEXT[] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation.valuation_snapshots (
    id BIGSERIAL PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    token_id TEXT NOT NULL,
    condition_id TEXT,
    quantity NUMERIC NOT NULL,
    average_cost NUMERIC NOT NULL,
    mark_price NUMERIC NOT NULL,
    mark_reason TEXT NOT NULL,
    realized_pnl NUMERIC NOT NULL,
    unrealized_pnl NUMERIC NOT NULL,
    core_pnl NUMERIC NOT NULL,
    reward_pnl NUMERIC NOT NULL DEFAULT 0,
    total_pnl NUMERIC NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sim_orders_strategy
    ON simulation.orders (strategy_id);
CREATE INDEX IF NOT EXISTS idx_sim_orders_token
    ON simulation.orders (token_id);
CREATE INDEX IF NOT EXISTS idx_sim_fills_order
    ON simulation.fills (client_order_id);
CREATE INDEX IF NOT EXISTS idx_sim_cash_strategy
    ON simulation.cash_ledger (strategy_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sim_position_strategy_token
    ON simulation.position_ledger (strategy_id, token_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sim_risk_order
    ON simulation.risk_decisions (client_order_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sim_valuation_strategy_token
    ON simulation.valuation_snapshots (strategy_id, token_id, created_at DESC);

CREATE OR REPLACE VIEW views.simulation_positions AS
SELECT
    strategy_id,
    token_id,
    condition_id,
    SUM(delta) AS quantity
FROM simulation.position_ledger
GROUP BY strategy_id, token_id, condition_id;

CREATE OR REPLACE VIEW views.simulation_pnl AS
SELECT DISTINCT ON (strategy_id, token_id)
    strategy_id,
    token_id,
    condition_id,
    quantity,
    average_cost,
    mark_price,
    mark_reason,
    realized_pnl,
    unrealized_pnl,
    core_pnl,
    reward_pnl,
    total_pnl,
    created_at
FROM simulation.valuation_snapshots
ORDER BY strategy_id, token_id, created_at DESC;
