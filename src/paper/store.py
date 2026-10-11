"""V4 paper trading ledger: virtual OPEN/CLOSED positions in SQLite.

Entry is stored cost-adjusted (apply_entry).
"""

import sqlite3


def paper_enabled(cfg: dict) -> bool:
    return bool(cfg.get("paper_trading", {}).get("enabled", True))


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    cur = conn.execute(sql, params)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def has_open(conn: sqlite3.Connection, asset: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM paper_positions WHERE asset=? AND status='OPEN' LIMIT 1",
        (asset,),
    ).fetchone()
    return row is not None


def open_position(conn: sqlite3.Connection, asset: str, **fields) -> int | None:
    """Insert an OPEN position. Returns row id, or None if one is already OPEN (dedup)."""
    if has_open(conn, asset):
        return None
    cols = ["asset", *fields.keys()]
    placeholders = ", ".join("?" for _ in cols)
    cur = conn.execute(
        f"INSERT INTO paper_positions ({', '.join(cols)}) VALUES ({placeholders})",
        (asset, *fields.values()),
    )
    conn.commit()
    return cur.lastrowid


def close_position(conn: sqlite3.Connection, pos_id: int, *, exit_ts: int,
                   exit_price: float, exit_reason: str) -> dict:
    """Mark OPEN position closed. exit_price is cost-adjusted; pnl derived from stored entry."""
    pos = _rows(conn, "SELECT * FROM paper_positions WHERE id=?", (pos_id,))[0]
    pnl_pct = (exit_price - pos["entry"]) / pos["entry"] * 100
    pnl_usd = (pos["position_usd"] or 0.0) * pnl_pct / 100
    conn.execute(
        "UPDATE paper_positions SET status='CLOSED', exit_ts=?, exit_price=?,"
        " exit_reason=?, pnl_pct=?, pnl_usd=? WHERE id=?",
        (exit_ts, exit_price, exit_reason, pnl_pct, pnl_usd, pos_id),
    )
    conn.commit()
    return _rows(conn, "SELECT * FROM paper_positions WHERE id=?", (pos_id,))[0]


def list_open(conn: sqlite3.Connection) -> list[dict]:
    return _rows(conn, "SELECT * FROM paper_positions WHERE status='OPEN' ORDER BY open_ts")


def list_closed(conn: sqlite3.Connection) -> list[dict]:
    return _rows(conn, "SELECT * FROM paper_positions WHERE status='CLOSED' ORDER BY open_ts")


def count_open(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM paper_positions WHERE status='OPEN'").fetchone()[0]


def count_open_correlated(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM paper_positions WHERE status='OPEN' AND asset != 'BTC'"
    ).fetchone()[0]
