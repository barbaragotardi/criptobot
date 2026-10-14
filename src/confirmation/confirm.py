"""15m confirmation: closed candles only, configurable reversal rule."""

import pandas as pd


def confirm_reversal(df_15m: pd.DataFrame) -> tuple[bool, str]:
    """Bullish engulfing OR close above prior high. Closed candles assumed."""
    if len(df_15m) < 2:
        return False, "not_enough_candles"
    prev, cur = df_15m.iloc[-2], df_15m.iloc[-1]
    bullish_engulfing = cur["close"] > cur["open"] and prev["close"] < prev["open"] and cur["close"] >= prev["open"] and cur["open"] <= prev["close"]
    close_above_prior_high = cur["close"] > prev["high"]
    if bullish_engulfing:
        return True, "bullish_engulfing"
    if close_above_prior_high:
        return True, "close_above_prior_high"
    return False, "no_reversal"


def confirm_ema_reclaim(df_15m: pd.DataFrame, ema_value: float) -> tuple[bool, str]:
    """15m close back above the touched EMA. Closed candles assumed."""
    if len(df_15m) < 1 or ema_value is None:
        return False, "not_enough_candles"
    if float(df_15m.iloc[-1]["close"]) > ema_value:
        return True, "ema_reclaim"
    return False, "below_ema"


def confirm(df_15m: pd.DataFrame, method: str, ema_value: float | None = None) -> tuple[bool, str]:
    if method == "ema_reclaim":
        return confirm_ema_reclaim(df_15m, ema_value)
    if method == "any":
        ok, reason = confirm_reversal(df_15m)
        if ok:
            return True, reason
        return confirm_ema_reclaim(df_15m, ema_value)
    return confirm_reversal(df_15m)
