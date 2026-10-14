"""Postgres-only connection layer (Fase B).

Single database: Postgres via $DATABASE_URL / cfg['database_url'].
Timestamps are ms (~1.7e12) so BIGINT; prices need DOUBLE PRECISION
(PG REAL is 32-bit and loses precision).
"""

import os

SCHEMA = """
CREATE TABLE IF NOT EXISTS asset_state (
  asset TEXT PRIMARY KEY,
  state TEXT NOT NULL DEFAULT 'NO_SETUP',
  ema BIGINT,
  pullback_low DOUBLE PRECISION,
  entry DOUBLE PRECISION,
  stop DOUBLE PRECISION,
  tp DOUBLE PRECISION,
  rr DOUBLE PRECISION,
  watching_since_ts BIGINT,
  candles_15m_waited BIGINT DEFAULT 0,
  last_alert_ts BIGINT,
  cooldown_until_ts BIGINT,
  last_candle_ts_1d BIGINT,
  last_candle_ts_4h BIGINT,
  last_candle_ts_15m BIGINT,
  signals_today BIGINT DEFAULT 0,
  signals_day TEXT
);
CREATE TABLE IF NOT EXISTS daily_signals (
  day TEXT PRIMARY KEY,
  count BIGINT DEFAULT 0
);
CREATE TABLE IF NOT EXISTS paper_positions (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  asset TEXT NOT NULL,
  open_ts BIGINT NOT NULL,
  ema BIGINT,
  entry DOUBLE PRECISION NOT NULL,
  stop DOUBLE PRECISION NOT NULL,
  tp DOUBLE PRECISION NOT NULL,
  rr DOUBLE PRECISION,
  position_usd DOUBLE PRECISION,
  capital_risk DOUBLE PRECISION,
  stop_method TEXT,
  confirm_method TEXT,
  btc_bullish BIGINT,
  status TEXT NOT NULL DEFAULT 'OPEN',
  exit_ts BIGINT,
  exit_price DOUBLE PRECISION,
  exit_reason TEXT,
  pnl_pct DOUBLE PRECISION,
  pnl_usd DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_paper_status ON paper_positions(status);
CREATE TABLE IF NOT EXISTS portfolio_trades (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  asset TEXT NOT NULL,
  side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
  trade_ts BIGINT NOT NULL,
  quantity DOUBLE PRECISION NOT NULL,
  price DOUBLE PRECISION NOT NULL,
  cost_usd DOUBLE PRECISION NOT NULL,
  price_fallback BIGINT DEFAULT 0,
  created_ts BIGINT NOT NULL,
  telegram_message_id BIGINT,
  alert5_sent BIGINT DEFAULT 0,
  alert10_sent BIGINT DEFAULT 0,
  remaining_qty DOUBLE PRECISION
);
CREATE TABLE IF NOT EXISTS portfolio_fifo_matches (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  asset TEXT NOT NULL,
  buy_trade_id BIGINT NOT NULL,
  sell_trade_id BIGINT NOT NULL,
  qty DOUBLE PRECISION NOT NULL,
  buy_price DOUBLE PRECISION NOT NULL,
  sell_price DOUBLE PRECISION NOT NULL,
  pnl_usd DOUBLE PRECISION NOT NULL,
  pnl_pct DOUBLE PRECISION NOT NULL,
  matched_ts BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS portfolio_alert_state (
  asset TEXT NOT NULL,
  side TEXT NOT NULL,
  last_threshold_hit DOUBLE PRECISION DEFAULT 0,
  PRIMARY KEY (asset, side)
);
CREATE TABLE IF NOT EXISTS telegram_offset (
  id BIGINT PRIMARY KEY CHECK (id = 1),
  last_update_id BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS news_articles (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL DEFAULT '',
  published_at TIMESTAMPTZ,
  category TEXT NOT NULL DEFAULT 'general',
  tags TEXT[] NOT NULL DEFAULT '{}',
  fetched_ts BIGINT NOT NULL DEFAULT 0,
  embedding TEXT,
  embedding_model TEXT,
  embedding_dim BIGINT
);
CREATE INDEX IF NOT EXISTS idx_news_published ON news_articles(published_at);
CREATE TABLE IF NOT EXISTS council_reports (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  asset TEXT NOT NULL,
  ts BIGINT NOT NULL,
  setup_json TEXT NOT NULL DEFAULT '{}',
  news_json TEXT NOT NULL DEFAULT '{}',
  risk_json TEXT NOT NULL DEFAULT '{}',
  briefing_json TEXT NOT NULL DEFAULT '{}',
  model TEXT NOT NULL DEFAULT '',
  ok BIGINT NOT NULL DEFAULT 0,
  error TEXT NOT NULL DEFAULT '',
  trace_id TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_council_asset ON council_reports(asset);
CREATE TABLE IF NOT EXISTS ai_calls (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ts BIGINT NOT NULL,
  agent TEXT NOT NULL,
  model TEXT NOT NULL DEFAULT '',
  latency_ms BIGINT NOT NULL DEFAULT 0,
  prompt_tokens BIGINT NOT NULL DEFAULT 0,
  completion_tokens BIGINT NOT NULL DEFAULT 0,
  cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
  ok BIGINT NOT NULL DEFAULT 0,
  error TEXT NOT NULL DEFAULT ''
);
"""


def resolve_database_url(cfg: dict) -> str:
    """Precedence: cfg['database_url'] > $DATABASE_URL > cfg['system']['database_url']."""
    if cfg.get("database_url"):
        return str(cfg["database_url"])
    env = os.getenv("DATABASE_URL", "")
    if env:
        return env
    sys_cfg = cfg.get("system", {}) if isinstance(cfg.get("system"), dict) else {}
    return str(sys_cfg.get("database_url", "") or "")


def ensure_schema(conn, ai_enabled: bool = False, embedding_dim: int = 768) -> None:
    for stmt in SCHEMA.split(";"):
        if stmt.strip():
            conn.execute(stmt)
    conn.commit()
    _migrate_portfolio_remaining_qty(conn)
    _migrate_council_trace_id(conn)
    if ai_enabled:
        _migrate_ai_vector(conn, embedding_dim)


def _migrate_ai_vector(conn, embedding_dim: int) -> None:
    """CREATE EXTENSION vector + embedding vector column. Fail loud on mismatch."""
    import logging
    log = logging.getLogger(__name__)
    try:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.warning("pgvector extension unavailable, RAG falls back to SQL: %s", e)
        return
    row = conn.execute(
        "SELECT data_type, udt_name FROM information_schema.columns "
        "WHERE table_name='news_articles' AND column_name='embedding'"
    ).fetchone()
    if row and row[0] == "USER-DEFINED":
        return  # vector column already created by a previous run
    # Fresh table (TEXT placeholder above) -> convert to vector(dim).
    if row and row[0] == "text":
        conn.execute(
            f"ALTER TABLE news_articles ALTER COLUMN embedding TYPE vector({int(embedding_dim)}) "
            "USING CASE WHEN embedding IS NULL THEN NULL ELSE embedding::vector END"
        )
        conn.commit()
    try:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_news_embedding "
            "ON news_articles USING hnsw (embedding vector_cosine_ops)"
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.warning("hnsw index skipped: %s", e)


def _migrate_council_trace_id(conn) -> None:
    """trace_id links a briefing row to its Langfuse trace (LLMOps audit)."""
    row = conn.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='council_reports' AND column_name='trace_id'"
    ).fetchone()
    if not row:
        conn.execute("ALTER TABLE council_reports ADD COLUMN trace_id TEXT NOT NULL DEFAULT ''")
    conn.commit()


def _migrate_portfolio_remaining_qty(conn) -> None:
    """Backfill remaining_qty for DBs created before the FIFO feature."""
    row = conn.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='portfolio_trades' AND column_name='remaining_qty'"
    ).fetchone()
    if not row:
        conn.execute("ALTER TABLE portfolio_trades ADD COLUMN remaining_qty DOUBLE PRECISION")
    conn.execute(
        "UPDATE portfolio_trades SET remaining_qty = quantity "
        "WHERE remaining_qty IS NULL"
    )
    conn.execute(
        "UPDATE portfolio_trades SET remaining_qty = 0 "
        "WHERE side = 'BUY' AND remaining_qty IS NOT NULL "
        "AND ABS(remaining_qty) < 1e-9"
    )
    conn.commit()


def get_conn(cfg: dict):
    """Entry point. Requires a postgres* DATABASE_URL, fails loud otherwise."""
    url = resolve_database_url(cfg)
    if not url or not (
        url.startswith("postgres://") or url.startswith("postgresql://")
    ):
        raise RuntimeError(
            "DATABASE_URL must be a postgres* URL."
        )
    import psycopg  # lazy: keeps import cost off module load

    conn = psycopg.connect(url)
    ai = cfg.get("ai", {}) if isinstance(cfg.get("ai"), dict) else {}
    ensure_schema(conn, ai_enabled=bool(ai.get("enabled", False)),
                  embedding_dim=int(ai.get("embedding_dim", 768)))
    return conn
