"""Resolve trade price from Binance at the informed local time (HH:MM, today)."""

import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)


def _current_price(exchange, symbol: str) -> float:
    try:
        return float(exchange.fetch_ticker(symbol)["last"])
    except Exception:
        raw = exchange.fetch_ohlcv(symbol, timeframe="1m", limit=2)
        return float(raw[-1][4])


def price_at_dt(exchange, symbol: str, local_dt, cfg: dict) -> tuple[float, int, bool]:
    """Return (price, trade_ts_ms, fallback) for an explicit local datetime.

    Uses the nearest closed 1m candle at or before local_dt.
    Falls back to current price when the candle is not closed yet
    (datetime too recent or in the future).
    """
    trade_ts_ms = int(local_dt.timestamp() * 1000)
    now_ms = int(time.time() * 1000)

    if trade_ts_ms > now_ms - 60_000:
        return _current_price(exchange, symbol), trade_ts_ms, True

    raw = exchange.fetch_ohlcv(symbol, timeframe="1m",
                               since=trade_ts_ms - 5 * 60_000, limit=10)
    closed = [r for r in raw
              if r[0] + 60_000 <= now_ms and r[0] <= trade_ts_ms]
    if closed:
        return float(closed[-1][4]), trade_ts_ms, False
    log.warning("no closed 1m candle at %s for %s, using current price",
                local_dt.strftime("%d-%m-%Y-%H:%M"), symbol)
    return _current_price(exchange, symbol), trade_ts_ms, True


def price_at(exchange, symbol: str, hhmm: str, cfg: dict) -> tuple[float, int, bool]:
    """Return (price, trade_ts_ms, fallback) for HH:MM today (local timezone)."""
    tz = ZoneInfo(cfg["system"].get("timezone", "America/Sao_Paulo"))
    now_local = datetime.now(tz)
    hh, mm = int(hhmm.split(":")[0]), int(hhmm.split(":")[1])
    local_dt = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return price_at_dt(exchange, symbol, local_dt, cfg)
