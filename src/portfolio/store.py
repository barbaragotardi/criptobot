"""Portfolio ledger: record/list trades + weighted average price."""

import logging
import time

log = logging.getLogger(__name__)

# Quantities below this are float dust (e.g. 1e-08 left after FIFO) and
# are treated as zero everywhere (filters, display, sells).
EPS_QTY = 1e-9


def _clamp_dust(qty: float) -> float:
    return 0.0 if qty is None or abs(qty) <= EPS_QTY else float(qty)


def record_trade(conn, asset: str, side: str, trade_ts_ms: int, qty: float,
                 price: float, fallback: bool, message_id: int | None = None,
                 commit: bool = True) -> int:
    cur = conn.execute(
        "INSERT INTO portfolio_trades "
        "(asset, side, trade_ts, quantity, price, cost_usd, price_fallback, "
        " created_ts, telegram_message_id, remaining_qty) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (asset, side, trade_ts_ms, qty, price, qty * price,
         int(fallback), int(time.time()), message_id, qty),
    )
    if commit:
        conn.commit()
    log.info("Portfolio %s %s qty=%.6g @ %.2f", side, asset, qty, price)
    row = cur.fetchone()
    return row[0] if row else None


def list_trades(conn, asset: str | None = None) -> list[dict]:
    q = "SELECT * FROM portfolio_trades"
    args: tuple = ()
    if asset:
        q += " WHERE asset=%s"
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
            "WHERE asset=%s AND side='BUY' AND remaining_qty > %s",
            (asset, EPS_QTY),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT SUM(quantity * price), SUM(quantity) FROM portfolio_trades "
            "WHERE asset=%s AND side=%s",
            (asset, side),
        ).fetchone()
    if not row or not row[1]:
        return 0.0, 0.0
    qty = _clamp_dust(row[1])
    if not qty:
        return 0.0, 0.0
    return row[0] / row[1], qty


def open_buy_qty(conn, asset: str) -> float:
    """Total BUY quantity still open (not consumed by FIFO) for asset."""
    row = conn.execute(
        "SELECT SUM(remaining_qty) FROM portfolio_trades "
        "WHERE asset=%s AND side='BUY' AND remaining_qty > %s",
        (asset, EPS_QTY),
    ).fetchone()
    return _clamp_dust(float(row[0] or 0.0))


def consume_fifo(conn, asset: str, sell_trade_id: int, sell_qty: float,
                 sell_price: float, commit: bool = True) -> list[dict]:
    """Match a SELL against open BUY lots (oldest trade_ts first).

    Caller must have validated sell_qty <= open_buy_qty. Raises RuntimeError
    if lots run out (fail loud: never leave a sale partially unmatched).
    """
    lots = conn.execute(
        "SELECT id, remaining_qty, price FROM portfolio_trades "
        "WHERE asset=%s AND side='BUY' AND remaining_qty > %s "
        "ORDER BY trade_ts ASC, id ASC",
        (asset, EPS_QTY),
    ).fetchall()
    matches: list[dict] = []
    left = sell_qty
    for lot_id, remaining, buy_price in lots:
        if left <= EPS_QTY:
            break
        take = min(remaining, left)
        pnl = take * (sell_price - buy_price)
        new_remaining = remaining - take
        if abs(new_remaining) <= EPS_QTY:
            new_remaining = 0.0
        conn.execute(
            "UPDATE portfolio_trades SET remaining_qty = %s WHERE id=%s",
            (new_remaining, lot_id),
        )
        conn.execute(
            "INSERT INTO portfolio_fifo_matches "
            "(asset, buy_trade_id, sell_trade_id, qty, buy_price, sell_price, "
            " pnl_usd, pnl_pct, matched_ts) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (asset, lot_id, sell_trade_id, take, buy_price, sell_price,
             pnl, (sell_price - buy_price) / buy_price * 100, int(time.time())),
        )
        matches.append({"buy_trade_id": lot_id, "qty": take,
                        "buy_price": buy_price, "pnl_usd": pnl,
                        "pnl_pct": (sell_price - buy_price) / buy_price * 100})
        left -= take
    if commit:
        conn.commit()
    if left > EPS_QTY:
        raise RuntimeError(
            f"FIFO underflow for {asset}: {left:g} unmatched "
            f"(open lots changed concurrently%s)"
        )
    log.info("FIFO %s sell #%d matched %d lot(s)", asset, sell_trade_id, len(matches))
    return matches


def realized_pnl(conn, asset: str) -> tuple[float, float]:
    """Return (total pnl_usd, total matched qty) from FIFO matches for asset."""
    row = conn.execute(
        "SELECT SUM(pnl_usd), SUM(qty) FROM portfolio_fifo_matches WHERE asset=%s",
        (asset,),
    ).fetchone()
    if not row or not row[1]:
        return 0.0, 0.0
    return float(row[0]), float(row[1])


def distinct_assets(conn) -> list[str]:
    rows = conn.execute("SELECT DISTINCT asset FROM portfolio_trades").fetchall()
    return [r[0] for r in rows]


def matches_for_asset(conn, asset: str) -> list[dict]:
    cols = [c[0] for c in conn.execute("SELECT * FROM portfolio_fifo_matches LIMIT 0").description]
    rows = conn.execute(
        "SELECT * FROM portfolio_fifo_matches WHERE asset=%s ORDER BY sell_trade_id, id",
        (asset,),
    ).fetchall()
    return [dict(zip(cols, r)) for r in rows]


def get_trade(conn, trade_id: int) -> dict | None:
    cols = [c[0] for c in conn.execute("SELECT * FROM portfolio_trades LIMIT 0").description]
    row = conn.execute("SELECT * FROM portfolio_trades WHERE id=%s", (trade_id,)).fetchone()
    return dict(zip(cols, row)) if row else None


def delete_trade(conn, trade_id: int, commit: bool = True) -> None:
    conn.execute("DELETE FROM portfolio_trades WHERE id=%s", (trade_id,))
    if commit:
        conn.commit()


def update_trade_qty(conn, trade_id: int, qty: float, commit: bool = True) -> None:
    conn.execute(
        "UPDATE portfolio_trades SET quantity=%s, cost_usd=%s*price, "
        "alert5_sent=0, alert10_sent=0 WHERE id=%s",
        (qty, qty, trade_id),
    )
    if commit:
        conn.commit()


def update_trade_price(conn, trade_id: int, price: float, commit: bool = True) -> None:
    conn.execute(
        "UPDATE portfolio_trades SET price=%s, cost_usd=quantity*%s, "
        "price_fallback=0, alert5_sent=0, alert10_sent=0 WHERE id=%s",
        (price, price, trade_id),
    )
    if commit:
        conn.commit()


def update_trade_time(conn, trade_id: int, trade_ts_ms: int, price: float,
                      fallback: bool, commit: bool = True) -> None:
    conn.execute(
        "UPDATE portfolio_trades SET trade_ts=%s, price=%s, cost_usd=quantity*%s, "
        "price_fallback=%s, alert5_sent=0, alert10_sent=0 WHERE id=%s",
        (trade_ts_ms, price, price, int(fallback), trade_id),
    )
    if commit:
        conn.commit()


def recompute_fifo(conn, asset: str, commit: bool = True) -> None:
    """Rebuild FIFO matches for asset from scratch.

    Deletes existing matches, resets remaining_qty on BUY lots, and replays
    all SELLs in chronological order. On underflow, rolls back everything
    and raises ValueError (user-facing).
    """
    sells = conn.execute(
        "SELECT id, quantity, price FROM portfolio_trades "
        "WHERE asset=%s AND side='SELL' ORDER BY trade_ts ASC, id ASC",
        (asset,),
    ).fetchall()
    conn.execute("DELETE FROM portfolio_fifo_matches WHERE asset=%s", (asset,))
    conn.execute(
        "UPDATE portfolio_trades SET remaining_qty=quantity "
        "WHERE asset=%s AND side='BUY'",
        (asset,),
    )
    try:
        for sell_id, sell_qty, sell_price in sells:
            consume_fifo(conn, asset, sell_id, sell_qty, sell_price, commit=False)
    except RuntimeError:
        conn.rollback()
        raise ValueError(
            f"Operação rejeitada: {asset} ficaria com venda sem lote de "
            "compra suficiente para abater. Nada foi alterado."
        )
    if commit:
        conn.commit()
    log.info("FIFO recompute %s: %d sell(s) replayed", asset, len(sells))
