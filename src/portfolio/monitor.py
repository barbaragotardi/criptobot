"""Per-cycle portfolio alert check: weighted avg + individual trades, 5%/10%."""

import logging

from src.alerts.telegram import format_portfolio_alert, send_telegram
from src.exchange.client import fetch_ohlcv, symbol_for
from src.portfolio.store import EPS_QTY, distinct_assets, list_trades, weighted_avg

log = logging.getLogger(__name__)


def _thresholds(cfg: dict) -> tuple[float, float]:
    th = cfg.get("portfolio", {}).get("thresholds_percent", [5.0, 10.0])
    return float(th[0]), float(th[1])


def _last_hit(conn, asset: str, side: str) -> float:
    row = conn.execute(
        "SELECT last_threshold_hit FROM portfolio_alert_state WHERE asset=? AND side=?",
        (asset, side),
    ).fetchone()
    return float(row[0]) if row else 0.0


def _set_hit(conn, asset: str, side: str, value: float) -> None:
    conn.execute(
        "INSERT INTO portfolio_alert_state (asset, side, last_threshold_hit) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT(asset, side) DO UPDATE SET last_threshold_hit=excluded.last_threshold_hit",
        (asset, side, value),
    )
    conn.commit()


def _variation(side: str, ref: float, current: float) -> float:
    """Favorable-direction variation only: gain for BUY, drop for SELL."""
    if side == "BUY":
        return (current - ref) / ref * 100
    return (ref - current) / ref * 100


def check_portfolio_alerts(conn, exchange, cfg) -> list[dict]:
    """Check all assets with trades against current price. Returns fired alerts."""
    if not cfg.get("portfolio", {}).get("enabled", True):
        return []
    t5, t10 = _thresholds(cfg)
    tg = cfg["telegram"]
    dry_run = cfg["system"].get("dry_run", True)
    quote = cfg["system"]["quote_currency"]
    fired: list[dict] = []

    for asset in distinct_assets(conn):
        try:
            df = fetch_ohlcv(exchange, symbol_for(asset, quote),
                             cfg["timeframe_map"]["15m"], 1)
            current = float(df.iloc[-1]["close"])
        except Exception as e:
            log.warning("portfolio price %s failed: %s", asset, e)
            continue

        for side in ("BUY", "SELL"):
            # --- weighted average scope ---
            avg, qty = weighted_avg(conn, asset, side)
            if qty:
                pct = _variation(side, avg, current)
                last = _last_hit(conn, asset, side)
                hit = t10 if pct >= t10 and last < t10 else (t5 if pct >= t5 and last < t5 else 0)
                if hit:
                    text = format_portfolio_alert(asset, side, avg, current, pct, hit, "media")
                    if send_telegram(tg["bot_token"], tg["chat_id"], text, dry_run=dry_run):
                        _set_hit(conn, asset, side, hit)
                        fired.append({"asset": asset, "side": side, "scope": "media",
                                      "threshold": hit, "pct": round(pct, 2)})
                        log.info("%s %s avg alert %.0f%% (var %.1f%%)", asset, side, hit, pct)
                elif pct < t5 and last != 0:
                    _set_hit(conn, asset, side, 0.0)

            # --- individual trade scope (fires once per threshold) ---
            for tr in [t for t in list_trades(conn, asset) if t["side"] == side]:
                if side == "BUY" and (tr.get("remaining_qty") or 0) <= EPS_QTY:
                    continue  # lot fully sold via FIFO: nothing held, no alert
                pct = _variation(side, tr["price"], current)
                col = None
                if pct >= t10 and not tr["alert10_sent"]:
                    col, hit = "alert10_sent", t10
                elif pct >= t5 and not tr["alert5_sent"] and pct < t10:
                    col, hit = "alert5_sent", t5
                if col:
                    text = format_portfolio_alert(asset, side, tr["price"], current,
                                                  pct, hit, "individual")
                    if send_telegram(tg["bot_token"], tg["chat_id"], text, dry_run=dry_run):
                        if col == "alert10_sent":
                            conn.execute("UPDATE portfolio_trades SET alert5_sent=1, alert10_sent=1 WHERE id=?", (tr["id"],))
                        else:
                            conn.execute(f"UPDATE portfolio_trades SET {col}=1 WHERE id=?", (tr["id"],))
                        conn.commit()
                        fired.append({"asset": asset, "side": side, "scope": "individual",
                                      "trade_id": tr["id"], "threshold": hit,
                                      "pct": round(pct, 2)})
                        log.info("%s trade #%d alert %.0f%% (var %.1f%%)",
                                 asset, tr["id"], hit, pct)
    return fired
