"""V4 exit monitor: checks OPEN paper positions against the latest closed 15m candle.

Same rule as backtest exit_simulator (same-candle stop+TP -> STOP), but
incremental: one closed candle per cycle instead of a full history walk.
"""

import logging

from src.alerts.telegram import format_paper_close, send_telegram
from src.backtest.costs import apply_exit
from src.exchange.client import TF_MS, fetch_ohlcv, symbol_for
from src.paper.store import close_position, list_open, paper_enabled

log = logging.getLogger(__name__)


def check_open_positions(conn, exchange, cfg: dict) -> list[dict]:
    """Check every OPEN position against its latest closed 15m candle. Returns closed rows."""
    if not paper_enabled(cfg):
        return []
    quote = cfg["system"]["quote_currency"]
    tf = cfg["timeframe_map"]["15m"]
    closed = []
    for pos in list_open(conn):
        try:
            df = fetch_ohlcv(exchange, symbol_for(pos["asset"], quote), tf, limit=2)
        except Exception as e:
            log.warning("%s - paper monitor fetch failed: %s", pos["asset"], e)
            continue
        candle = df.iloc[-1]
        stop_hit = candle["low"] <= pos["stop"]
        tp_hit = candle["high"] >= pos["tp"]
        if stop_hit:
            reason, raw = "STOP", pos["stop"]
        elif tp_hit:
            reason, raw = "TP", pos["tp"]
        else:
            continue
        exit_ts = int(candle["ts"]) + TF_MS["15m"]
        row = close_position(conn, pos["id"], exit_ts=exit_ts,
                             exit_price=apply_exit(raw, cfg), exit_reason=reason)
        log.info("%s - PAPER CLOSED #%d %s %+0.2f%%", pos["asset"], pos["id"],
                 reason, row["pnl_pct"])
        tg = cfg["telegram"]
        text = format_paper_close(pos["asset"], reason, row["exit_price"],
                                  row["pnl_pct"], row["pnl_usd"])
        if not send_telegram(tg["bot_token"], tg["chat_id"], text,
                             dry_run=cfg["system"].get("dry_run", True)):
            log.warning("%s - paper close alert NOT sent", pos["asset"])
        closed.append(row)
    return closed
