"""Portfolio ledger: record/list trades + weighted average price."""

import logging
import time

log = logging.getLogger(__name__)


def record_trade(conn, asset: str, side: str, trade_ts_ms: int, qty: float,
                 price: float, fallback: bool, message_id: int | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO portfolio_trades "
        "(asset, side, trade_ts, quantity, price, cost_usd, price_fallback, "
        " created_ts, telegram_message_id, remaining_qty) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (asset, side, trade_ts_ms, qty, price, qty * price,
         int(fallback), int(time.time()), message_id, qty),
    )
    conn.commit()
    log.info("Portfolio %s %s qty=%.6g @ %.2f", side, asset, qty, price)
    return cur.lastrowid


def list_trades(conn, asset: str | None = None) -> list[dict]:
    q = "SELECT * FROM portfolio_trades"
    args: tuple = ()
    if asset:
        q += " WHERE asset=?"
        args = (asset,)
    q += " ORDER BY id"
    cols = [c[0] for c in conn.execute("SELECT * FROM portfolio_trades LIMIT 0").description]
    return [dict(zip(cols, r)) for r in conn.execute(q, args).fetchall()]


def weighted_avg(conn, asset: str, side: str) -> tuple[float, float]:
    """Return (avg_price, total_qty) weighted by quantity for asset+side.

    BUY scope covers open lots only (remaining_qty > 0); sold quantity
    no longer counts after FIFO consumption.
    """
    if side == "BUY":
        row = conn.execute(
            "SELECT SUM(remaining_qty * price), SUM(remaining_qty) FROM portfolio_trades "
            "WHERE asset=? AND side='BUY' AND remaining_qty > 0",
            (asset,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT SUM(quantity * price), SUM(quantity) FROM portfolio_trades "
            "WHERE asset=? AND side=?",
            (asset, side),
        ).fetchone()
    if not row or not row[1]:
        return 0.0, 0.0
    return row[0] / row[1], row[1]


def open_buy_qty(conn, asset: str) -> float:
    """Total BUY quantity still open (not consumed by FIFO) for asset."""
    row = conn.execute(
        "SELECT SUM(remaining_qty) FROM portfolio_trades "
        "WHERE asset=? AND side='BUY' AND remaining_qty > 0",
        (asset,),
    ).fetchone()
    return float(row[0] or 0.0)


def consume_fifo(conn, asset: str, sell_trade_id: int, sell_qty: float,
                 sell_price: float) -> list[dict]:
    """Match a SELL against open BUY lots (oldest trade_ts first).

    Caller must have validated sell_qty <= open_buy_qty. Raises RuntimeError
    if lots run out (fail loud: never leave a sale partially unmatched).
    """
    lots = conn.execute(
        "SELECT id, remaining_qty, price FROM portfolio_trades "
        "WHERE asset=? AND side='BUY' AND remaining_qty > 0 "
        "ORDER BY trade_ts ASC, id ASC",
        (asset,),
    ).fetchall()
    matches: list[dict] = []
    left = sell_qty
    for lot_id, remaining, buy_price in lots:
        if left <= 0:
            break
        take = min(remaining, left)
        pnl = take * (sell_price - buy_price)
        conn.execute(
            "UPDATE portfolio_trades SET remaining_qty = remaining_qty - ? WHERE id=?",
            (take, lot_id),
        )
        conn.execute(
            "INSERT INTO portfolio_fifo_matches "
            "(asset, buy_trade_id, sell_trade_id, qty, buy_price, sell_price, "
            " pnl_usd, pnl_pct, matched_ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (asset, lot_id, sell_trade_id, take, buy_price, sell_price,
             pnl, (sell_price - buy_price) / buy_price * 100, int(time.time())),
        )
        matches.append({"buy_trade_id": lot_id, "qty": take,
                        "buy_price": buy_price, "pnl_usd": pnl,
                        "pnl_pct": (sell_price - buy_price) / buy_price * 100})
        left -= take
    conn.commit()
    if left > 1e-9:
        raise RuntimeError(
            f"FIFO underflow for {asset}: {left:g} unmatched "
            f"(open lots changed concurrently?)"
        )
    log.info("FIFO %s sell #%d matched %d lot(s)", asset, sell_trade_id, len(matches))
    return matches


def realized_pnl(conn, asset: str) -> tuple[float, float]:
    """Return (total pnl_usd, total matched qty) from FIFO matches for asset."""
    row = conn.execute(
        "SELECT SUM(pnl_usd), SUM(qty) FROM portfolio_fifo_matches WHERE asset=?",
        (asset,),
    ).fetchone()
    if not row or not row[1]:
        return 0.0, 0.0
    return float(row[0]), float(row[1])


def distinct_assets(conn) -> list[str]:
    rows = conn.execute("SELECT DISTINCT asset FROM portfolio_trades").fetchall()
    return [r[0] for r in rows]
