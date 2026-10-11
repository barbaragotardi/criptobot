"""EMA + ATR indicators for the live signal engine."""

import pandas as pd


def add_ema(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    out = df.copy()
    for p in periods:
        out[f"ema{p}"] = out["close"].ewm(span=p, adjust=True, min_periods=p).mean()
    return out


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    out = df.copy()
    prev_close = out["close"].shift(1)
    tr = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - prev_close).abs(),
            (out["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["atr"] = tr.ewm(span=period, adjust=True, min_periods=period).mean()
    return out


def add_indicators(df: pd.DataFrame, ema_periods: list[int], atr_period: int) -> pd.DataFrame:
    return add_atr(add_ema(df, ema_periods), atr_period)
