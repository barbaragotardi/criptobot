"""Pullback 4H detection: EMA20>EMA50 trend + touch of EMA20/50 zone."""

import logging
import pandas as pd

log = logging.getLogger(__name__)


def detect_pullback(df_4h: pd.DataFrame, cfg: dict) -> dict:
    """Returns {valid, ema, distance_pct, pullback_low}. No-trade default."""
    entry_cfg = cfg["entry"]
    row = df_4h.iloc[-1]
    if not row["ema20"] > row["ema50"]:
        return {"valid": False, "reason": "ema20<=ema50_4h"}

    price = row["close"]
    atr = row.get("atr")
    best = None
    for ema_period in entry_cfg.get("allowed_emas", [20, 50]):
        ema_val = row[f"ema{ema_period}"]
        dist_pct = abs(price - ema_val) / price * 100
        touched = dist_pct <= entry_cfg.get("touch_threshold_percent", 1.0)
        if entry_cfg.get("use_atr_distance", True) and atr and pd.notna(atr):
            touched = touched or (abs(price - ema_val) <= atr * entry_cfg.get("atr_k", 0.5))
        if touched and (best is None or dist_pct < best["distance_pct"]):
            best = {"ema": ema_period, "distance_pct": dist_pct}

    if best is None:
        return {"valid": False, "reason": "no_ema_touch"}
    window = df_4h.iloc[-6:]
    pullback_low = float(window["low"].min())
    log.info("4H EMA%(ema)s touch detected (dist %(dist).2f%%)", {"ema": best["ema"], "dist": best["distance_pct"]})
    return {"valid": True, "ema": best["ema"], "distance_pct": best["distance_pct"], "pullback_low": pullback_low}
