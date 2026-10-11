"""Market filter (BTC, once per cycle) + macro 1D filter per asset."""

import logging
import pandas as pd

log = logging.getLogger(__name__)


def ema_slope_up(series: pd.Series, periods: int) -> bool:
    if len(series) < periods + 1:
        return False
    return bool(series.iloc[-1] > series.iloc[-(periods + 1)])


def macro_pass(df_1d: pd.DataFrame, cfg: dict) -> tuple[bool, str]:
    """Returns (passed, reason). Expects indicators already added."""
    m = cfg["macro"]
    row = df_1d.iloc[-1]
    if m.get("price_above_ema200", True) and not row["close"] > row["ema200"]:
        return False, "close<=ema200_1d"
    if m.get("ema200_slope_required", True) and not ema_slope_up(
        df_1d["ema200"], m.get("slope_periods", 5)
    ):
        return False, "ema200_slope_down"
    if m.get("ema20_above_ema50", True) and not row["ema20"] > row["ema50"]:
        return False, "ema20<=ema50_1d"
    return True, "ok"


def evaluate_market_filter(btc_1d: pd.DataFrame, cfg: dict) -> dict:
    """Compute once per cycle; assets reuse the returned dict."""
    mf = cfg["market_filter"]
    if not mf.get("enabled", True):
        return {"bullish": True, "reference_asset": "BTC", "reason": "disabled"}
    row = btc_1d.iloc[-1]
    bullish = bool(row["close"] > row["ema200"])
    log.info("Market Filter - BTC: %s", "PASS" if bullish else "FAIL")
    return {"bullish": bullish, "reference_asset": "BTC", "reason": "close_vs_ema200"}
