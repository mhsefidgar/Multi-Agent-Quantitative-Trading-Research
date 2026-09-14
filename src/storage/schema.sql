-- Apply with a migration runner against the managed PostgreSQL instance.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS research_runs (
    run_id UUID PRIMARY KEY,
    trace_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'blocked')),
    risk_approved BOOLEAN,
    decision_hash TEXT
);

CREATE TABLE IF NOT EXISTS factor_observations (
    run_id UUID NOT NULL REFERENCES research_runs(run_id),
    ticker TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    factor_name TEXT NOT NULL,
    factor_value DOUBLE PRECISION NOT NULL,
    embedding vector(1536),
    PRIMARY KEY (run_id, observed_at, factor_name)
);

CREATE TABLE IF NOT EXISTS agent_messages (
    message_id BIGSERIAL PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES research_runs(run_id),
    trace_id TEXT NOT NULL,
    node_name TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES research_runs(run_id),
    trace_id TEXT NOT NULL,
    client_order_id TEXT NOT NULL UNIQUE,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity DOUBLE PRECISION NOT NULL CHECK (quantity > 0),
    requested_price DOUBLE PRECISION,
    status TEXT NOT NULL,
    filled_quantity DOUBLE PRECISION NOT NULL DEFAULT 0,
    average_fill_price DOUBLE PRECISION,
    slippage_bps DOUBLE PRECISION,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id BIGSERIAL PRIMARY KEY,
    run_id UUID REFERENCES research_runs(run_id),
    trace_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS factor_observations_embedding_idx
    ON factor_observations USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;
CREATE INDEX IF NOT EXISTS agent_messages_run_idx ON agent_messages(run_id, created_at);
CREATE INDEX IF NOT EXISTS audit_events_trace_idx ON audit_events(trace_id, created_at);
