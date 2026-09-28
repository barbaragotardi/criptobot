"""Historical OHLCV cache: full history per asset/timeframe as parquet."""

import logging
from pathlib import Path

import ccxt
import pandas as pd

from src.exchange.client import TF_MS, make_exchange, symbol_for

log = logging.getLogger(__name__)

COLS = ["ts", "open", "high", "low", "close", "volume"]


def cache_path(base: str, asset: str, timeframe: str) -> Path:
    return Path(base) / f"{asset}_{timeframe}.parquet"


def fetch_full_history(exchange: ccxt.binance, symbol: str, timeframe: str) -> pd.DataFrame:
    """Paginate backwards from now to listing. Closed candles only."""
    step_1000 = TF_MS[timeframe] * 1000  # ms covered by 1000 candles
    latest = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=1000)
    all_rows = latest
    while len(latest) == 1000:
        since = max(latest[0][0] - step_1000, 0)
        latest = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=1000, since=since)
        latest = [c for c in latest if c[0] < all_rows[0][0]]
        if not latest:
            break
        all_rows = latest + all_rows
    df = pd.DataFrame(all_rows, columns=COLS).drop_duplicates("ts").sort_values("ts")
    df["datetime"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    # Drop last row: possibly still-open candle.
    return df.iloc[:-1].reset_index(drop=True)


def fetch_and_cache(cfg: dict, assets: list[str] | None = None, refresh: bool = False) -> None:
    exchange = make_exchange()
    base = cfg["backtest"]["data_dir"]
    Path(base).mkdir(parents=True, exist_ok=True)
    for asset in assets or cfg["assets"]:
        symbol = symbol_for(asset, cfg["system"]["quote_currency"])
        for tf_key, tf in cfg["timeframe_map"].items():
            p = cache_path(base, asset, tf_key)
            if p.exists() and not refresh:
                log.info("%s %s: cached (%s)", asset, tf_key, p)
                continue
            log.info("%s %s: downloading full history...", asset, tf_key)
            df = fetch_full_history(exchange, symbol, tf)
            df.to_parquet(p, index=False)
            log.info("%s %s: %d candles, %s -> %s", asset, tf_key, len(df),
                     df["datetime"].iloc[0].date(), df["datetime"].iloc[-1].date())


def load_cached(base: str, asset: str, timeframe_key: str) -> pd.DataFrame:
    return pd.read_parquet(cache_path(base, asset, timeframe_key))
