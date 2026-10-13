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


def ensure_schema(conn) -> None:
    for stmt in SCHEMA.split(";"):
        if stmt.strip():
            conn.execute(stmt)
    conn.commit()
    _migrate_portfolio_remaining_qty(conn)


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
    ensure_schema(conn)
    return conn
