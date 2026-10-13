"""Support levels: MA30/EMA30/pivot/Fibonacci with fractal swing anchors."""

import logging

log = logging.getLogger(__name__)


def _defaults(cfg: dict) -> dict:
    s = (cfg or {}).get("supports", {}) or {}
    return {
        "sma_short": int(s.get("sma_short", 30)),
        "sma_long": int(s.get("sma_long", 200)),
        "discovery_lookback": int(s.get("discovery_lookback", 90)),
        "fib_ratios": list(s.get("fib_ratios", [0.382, 0.5, 0.618, 0.786])),
        "fractal_k": int(s.get("fractal_k", 2)),
        "min_swing_move_percent": float(s.get("min_swing_move_percent", 10.0)),
        "use_wicks": bool(s.get("use_wicks", True)),
    }


def compute_ma(df, cfg: dict) -> dict:
    """Return sma_short, ema_short, sma_long + current price from closes."""
    p = _defaults(cfg)
    closes = df["close"].astype(float)
    n_short, n_long = p["sma_short"], p["sma_long"]
    out = {"current": float(closes.iloc[-1])}
    out["sma_short"] = float(closes.tail(n_short).mean()) if len(closes) >= n_short else None
    out["ema_short"] = float(closes.ewm(span=n_short, adjust=True, min_periods=n_short).mean().iloc[-1]) if len(closes) >= n_short else None
    out["sma_long"] = float(closes.tail(n_long).mean()) if len(closes) >= n_long else None
    return out


def compute_pivot(last) -> dict:
    """Daily pivot + S1/S2 from last closed candle (H/L/C)."""
    h, low, c = float(last["high"]), float(last["low"]), float(last["close"])
    piv = (h + low + c) / 3.0
    return {"p": piv, "s1": 2 * piv - h, "s2": piv - (h - low)}


def _swings(window, k: int, use_wicks: bool) -> tuple[list, list]:
    """Fractal swing highs/lows on discovery window. Returns index lists."""
    hi = window["high"].astype(float).tolist() if use_wicks else window["close"].astype(float).tolist()
    lo = window["low"].astype(float).tolist() if use_wicks else window["close"].astype(float).tolist()
    highs, lows = [], []
    for i in range(k, len(window) - k):
        if all(hi[i] > hi[j] for j in range(i - k, i + k + 1) if j != i):
            highs.append(i)
        if all(lo[i] < lo[j] for j in range(i - k, i + k + 1) if j != i):
            lows.append(i)
    return highs, lows


def _has_reaction(window, idx: int, kind: str) -> bool:
    """2-candle reaction: closes move away from the extreme."""
    closes = window["close"].astype(float).tolist()
    extreme = float(window["high"].iloc[idx]) if kind == "high" else float(window["low"].iloc[idx])
    nxt = closes[idx + 1:idx + 3]
    if len(nxt) < 2:
        return False
    if kind == "high":
        return all(c < extreme for c in nxt)
    return all(c > extreme for c in nxt)


def find_swing(df, cfg: dict) -> dict:
    """Most recent fractal impulse leg inside discovery window."""
    p = _defaults(cfg)
    k, lookback = p["fractal_k"], p["discovery_lookback"]
    window = df.tail(lookback).reset_index(drop=True)
    price_col = "high" if p["use_wicks"] else "close"
    low_col = "low" if p["use_wicks"] else "close"
    highs, lows = _swings(window, k, p["use_wicks"])
    if highs and lows:
        for hi in sorted(highs, reverse=True):
            prior_lows = [lo for lo in lows if lo < hi]
            for lo in sorted(prior_lows, reverse=True):
                high = float(window[price_col].iloc[hi])
                low = float(window[low_col].iloc[lo])
                if low <= 0 or high <= low:
                    continue
                move = (high - low) / low * 100.0
                if move < p["min_swing_move_percent"]:
                    continue
                if not _has_reaction(window, hi, "high"):
                    continue
                if not _has_reaction(window, lo, "low"):
                    continue
                return {
                    "high": high, "low": low,
                    "high_date": str(window["datetime"].iloc[hi]),
                    "low_date": str(window["datetime"].iloc[lo]),
                    "fallback": False,
                }
    high, low = float(window["high"].max()), float(window["low"].min())
    return {
        "high": high, "low": low,
        "high_date": str(window.loc[window["high"].idxmax(), "datetime"]),
        "low_date": str(window.loc[window["low"].idxmin(), "datetime"]),
        "fallback": True,
    }


def compute_fib(high: float, low: float, ratios: list, bullish: bool = True) -> dict:
    """Retracement levels. Bullish: High-(High-Low)*r; bearish: Low+(High-Low)*r."""
    out = {}
    for r in ratios:
        r = float(r)
        out[r] = high - (high - low) * r if bullish else low + (high - low) * r
    return out


def compute_supports(df, cfg: dict) -> dict:
    """Full support snapshot from closed daily candles."""
    p = _defaults(cfg)
    ma = compute_ma(df, cfg)
    last = df.iloc[-1]
    pivot = compute_pivot(last)
    swing = find_swing(df, cfg)
    bullish = ma["current"] >= (swing["high"] + swing["low"]) / 2.0
    fib = compute_fib(swing["high"], swing["low"], p["fib_ratios"], bullish=bullish)
    cluster = [v for v in [ma["sma_short"], ma["ema_short"], pivot["p"], fib.get(0.382)] if v]
    zone = (min(cluster), max(cluster)) if cluster else (None, None)
    log.info("supports swing %s -> %s fallback=%s bullish=%s",
             swing["low_date"], swing["high_date"], swing["fallback"], bullish)
    return {
        "current": ma["current"], "sma_short": ma["sma_short"],
        "ema_short": ma["ema_short"], "sma_long": ma["sma_long"],
        "pivot": pivot, "swing": swing, "fib": fib,
        "bullish": bullish, "zone": zone, "params": p,
    }
