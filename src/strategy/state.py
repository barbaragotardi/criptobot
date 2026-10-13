"""State machine + persistence (sections 25-27, 35). Postgres via src.db."""

import time

STATES = ("NO_SETUP", "TOUCHED_EMA", "WATCHING", "CONFIRMED", "ALERT_SENT", "INVALIDATED", "COOLDOWN")


def connect_cfg(cfg: dict):
    """Entry point: Postgres only (fails loud without DATABASE_URL)."""
    from src.db import get_conn

    return get_conn(cfg)


def get_state(conn, asset: str) -> dict:
    row = conn.execute("SELECT * FROM asset_state WHERE asset=%s", (asset,)).fetchone()
    if row is None:
        conn.execute("INSERT INTO asset_state (asset, state) VALUES (%s, 'NO_SETUP')", (asset,))
        conn.commit()
        return get_state(conn, asset)
    cols = [c[0] for c in conn.execute("SELECT * FROM asset_state LIMIT 0").description]
    return dict(zip(cols, row))


def set_state(conn, asset: str, **fields) -> None:
    get_state(conn, asset)  # ensure row exists
    cols = ", ".join(f"{k}=%s" for k in fields)
    conn.execute(f"UPDATE asset_state SET {cols} WHERE asset=%s", (*fields.values(), asset))
    conn.commit()


def in_cooldown(state: dict, now: int | None = None) -> bool:
    """`now` in epoch seconds. None = wall clock (production). Explicit ts is for tests/diagnostics."""
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
