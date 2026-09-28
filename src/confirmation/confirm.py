"""15m confirmation: closed candles only, configurable reversal rule (V1: 1 rule)."""

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
