"""Exposure manager (section 23). V4: caps count OPEN paper positions.

V1: all non-BTC assets share one correlated group."""

import sqlite3
import time


def _day(now: int | None) -> str:
    ts = now if now is not None else time.time()
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def exposure_ok(conn: sqlite3.Connection, asset: str, cfg: dict, now: int | None = None) -> tuple[bool, str]:
    exp = cfg["exposure"]
    open_signals = conn.execute(
        "SELECT COUNT(*) FROM paper_positions WHERE status='OPEN'").fetchone()[0]
    if open_signals >= exp["max_open_signals"]:
        return False, "max_open_signals"
    correlated = conn.execute(
        "SELECT COUNT(*) FROM paper_positions WHERE status='OPEN' AND asset != 'BTC'").fetchone()[0]
    if asset != "BTC" and correlated >= exp["max_correlated_exposure"]:
        return False, "max_correlated_exposure"
    today = _day(now)
    row = conn.execute("SELECT count FROM daily_signals WHERE day=?", (today,)).fetchone()
    if row and row[0] >= exp["max_signals_per_day"]:
        return False, "max_signals_per_day"
    return True, "ok"


def record_signal(conn: sqlite3.Connection, now: int | None = None) -> None:
    today = _day(now)
    conn.execute(
        "INSERT INTO daily_signals (day, count) VALUES (?, 1) "
        "ON CONFLICT(day) DO UPDATE SET count=count+1",
        (today,),
    )
    conn.commit()
