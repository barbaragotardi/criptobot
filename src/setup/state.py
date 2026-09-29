"""State machine + SQLite persistence (sections 25-27, 35)."""

import sqlite3
import time
from pathlib import Path

STATES = ("NO_SETUP", "TOUCHED_EMA", "WATCHING", "CONFIRMED", "ALERT_SENT", "INVALIDATED", "COOLDOWN")

SCHEMA = """
CREATE TABLE IF NOT EXISTS asset_state (
  asset TEXT PRIMARY KEY,
  state TEXT NOT NULL DEFAULT 'NO_SETUP',
  ema INTEGER,
  pullback_low REAL,
  entry REAL,
  stop REAL,
  tp REAL,
  rr REAL,
  watching_since_ts INTEGER,
  candles_15m_waited INTEGER DEFAULT 0,
  last_alert_ts INTEGER,
  cooldown_until_ts INTEGER,
  last_candle_ts_1d INTEGER,
  last_candle_ts_4h INTEGER,
  last_candle_ts_15m INTEGER,
  signals_today INTEGER DEFAULT 0,
  signals_day TEXT
);
CREATE TABLE IF NOT EXISTS daily_signals (
  day TEXT PRIMARY KEY,
  count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS paper_positions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asset TEXT NOT NULL,
  open_ts INTEGER NOT NULL,
  ema INTEGER,
  entry REAL NOT NULL,
  stop REAL NOT NULL,
  tp REAL NOT NULL,
  rr REAL,
  position_usd REAL,
  capital_risk REAL,
  stop_method TEXT,
  confirm_method TEXT,
  btc_bullish INTEGER,
  status TEXT NOT NULL DEFAULT 'OPEN',
  exit_ts INTEGER,
  exit_price REAL,
  exit_reason TEXT,
  pnl_pct REAL,
  pnl_usd REAL
);
CREATE INDEX IF NOT EXISTS idx_paper_status ON paper_positions(status);
CREATE TABLE IF NOT EXISTS portfolio_trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asset TEXT NOT NULL,
  side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
  trade_ts INTEGER NOT NULL,
  quantity REAL NOT NULL,
  price REAL NOT NULL,
  cost_usd REAL NOT NULL,
  price_fallback INTEGER DEFAULT 0,
  created_ts INTEGER NOT NULL,
  telegram_message_id INTEGER,
  alert5_sent INTEGER DEFAULT 0,
  alert10_sent INTEGER DEFAULT 0,
  remaining_qty REAL
);
CREATE TABLE IF NOT EXISTS portfolio_fifo_matches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  asset TEXT NOT NULL,
  buy_trade_id INTEGER NOT NULL,
  sell_trade_id INTEGER NOT NULL,
  qty REAL NOT NULL,
  buy_price REAL NOT NULL,
  sell_price REAL NOT NULL,
  pnl_usd REAL NOT NULL,
  pnl_pct REAL NOT NULL,
  matched_ts INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS portfolio_alert_state (
  asset TEXT NOT NULL,
  side TEXT NOT NULL,
  last_threshold_hit REAL DEFAULT 0,
  PRIMARY KEY (asset, side)
);
CREATE TABLE IF NOT EXISTS telegram_offset (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  last_update_id INTEGER NOT NULL DEFAULT 0
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    _migrate_portfolio_remaining_qty(conn)
    return conn


def _migrate_portfolio_remaining_qty(conn: sqlite3.Connection) -> None:
    """Backfill remaining_qty for DBs created before the FIFO feature."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(portfolio_trades)").fetchall()]
    if "remaining_qty" not in cols:
        conn.execute("ALTER TABLE portfolio_trades ADD COLUMN remaining_qty REAL")
    conn.execute(
        "UPDATE portfolio_trades SET remaining_qty = quantity "
        "WHERE remaining_qty IS NULL"
    )
    conn.commit()


def get_state(conn: sqlite3.Connection, asset: str) -> dict:
    row = conn.execute("SELECT * FROM asset_state WHERE asset=?", (asset,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO asset_state (asset, state) VALUES (?, 'NO_SETUP')", (asset,))
        conn.commit()
        return get_state(conn, asset)
    cols = [c[0] for c in conn.execute("SELECT * FROM asset_state LIMIT 0").description]
    return dict(zip(cols, row))


def set_state(conn: sqlite3.Connection, asset: str, **fields) -> None:
    get_state(conn, asset)  # ensure row exists
    cols = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE asset_state SET {cols} WHERE asset=?", (*fields.values(), asset))
    conn.commit()


def in_cooldown(state: dict, now: int | None = None) -> bool:
    """`now` in epoch seconds. None = wall clock (production). Backtest passes candle ts."""
    now = now if now is not None else int(time.time())
    return bool(state.get("cooldown_until_ts") and state["cooldown_until_ts"] > now)


def check_invalidation(df_4h, state: dict, cfg: dict) -> tuple[bool, str]:
    """Structural / pullback-low / macro rules (timeout handled by caller counter)."""
    inv = cfg["invalidation"]
    row = df_4h.iloc[-1]
    if inv.get("invalidate_below_ema50_4h") and row["close"] < row["ema50"]:
        return True, "close_below_ema50_4h"
    if inv.get("invalidate_below_pullback_low") and state.get("pullback_low") and row["close"] < state["pullback_low"]:
        return True, "close_below_pullback_low"
    return False, "ok"
