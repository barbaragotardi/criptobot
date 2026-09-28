"""ccxt Binance wrapper. Public data only, closed candles only."""

import logging
import time

import ccxt
import pandas as pd

log = logging.getLogger(__name__)

TF_MS = {"1d": 86_400_000, "4h": 14_400_000, "15m": 900_000}


def make_exchange() -> ccxt.binance:
    ex = ccxt.binance({"enableRateLimit": True})
    ex.load_markets()
    return ex


def symbol_for(asset: str, quote: str = "USDT") -> str:
    return f"{asset}/{quote}"


def fetch_ohlcv(
    exchange: ccxt.binance,
    symbol: str,
    timeframe: str,
    limit: int,
    retries: int = 3,
) -> pd.DataFrame:
    """Fetch OHLCV and drop the last (possibly still-open) candle."""
    last_exc = None
    for attempt in range(retries):
        try:
            raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit + 1)
            break
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            last_exc = e
            log.warning("fetch_ohlcv %s %s failed (attempt %d): %s", symbol, timeframe, attempt + 1, e)
            time.sleep(2 * (attempt + 1))
    else:
        raise last_exc

    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    # Drop last row: candle potentially still open.
    df = df.iloc[:-1].reset_index(drop=True)
    return df


def fetch_warmup(
    exchange: ccxt.binance,
    symbol: str,
    timeframe: str,
    total: int,
    quote: str = "USDT",
) -> pd.DataFrame:
    """Paginate backwards to accumulate `total` closed candles."""
    per_call = min(1000, total + 1)
    all_rows: list = []
    since = None
    while len(all_rows) < total + 1:
        raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=per_call, since=since)
        if not raw:
            break
        all_rows = raw + all_rows if since is not None else raw
        if len(raw) < per_call:
            break
        since = raw[0][0] - TF_MS[timeframe] * per_call
        if len(all_rows) >= total + 1:
            break
    # Keep only the most recent total+1, then drop the open one.
    rows = all_rows[-(total + 1):-1] if len(all_rows) > total else all_rows[:-1]
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df.reset_index(drop=True)
