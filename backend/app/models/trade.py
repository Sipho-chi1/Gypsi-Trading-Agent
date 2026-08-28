"""
Reference SQL schema — not wired to an ORM yet (raw SQL via SQLAlchemy
core is used in api/trades.py and worker/journal_writer.py for speed).
Run this against the Railway/local Postgres instance on Day 1.
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id               SERIAL PRIMARY KEY,
    symbol           TEXT NOT NULL,
    direction        TEXT,
    entry            NUMERIC,
    stop_loss        NUMERIC,
    take_profit      NUMERIC,
    reasoning        TEXT,
    verdict_decision TEXT NOT NULL,     -- approve | downsize | reject
    verdict_reason   TEXT,
    bias_flags       TEXT[],
    size_factor      NUMERIC DEFAULT 1.0,
    contract_expiry  DATE,
    contract_strike  NUMERIC,
    quantity         INTEGER,
    status           TEXT,               -- open | closed | skipped_zero_size | skipped
    pnl              NUMERIC,
    closed_at        TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades (symbol);
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades (created_at DESC);
"""
