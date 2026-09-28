"""Risk engine: stop (structure+ATR), resistance, TP, R/R, target class, sizing."""

# --- Stop: stop = pullback_low - ATR*K (project.md section 17) ---
def calc_stop(pullback_low: float, atr: float, atr_multiplier: float) -> float:
    return pullback_low - atr * atr_multiplier


# --- Resistance: max high of last N 4H candles (V1 proxy, section 18) ---
def find_resistance(df_4h, lookback: int) -> float:
    return float(df_4h.iloc[-lookback:]["high"].max())


# --- TP: min(resistance, entry*(1+preferred_max)); validations per section 19 ---
def calc_tp(entry: float, resistance: float, cfg: dict) -> tuple[float, str]:
    t = cfg["target"]
    cap = entry * (1 + t["preferred_max_percent"] / 100)
    tp = min(resistance, cap)
    ret_pct = (tp - entry) / entry * 100
    if ret_pct < t["absolute_min_percent"]:
        return tp, "REJECT"
    if ret_pct < t["preferred_min_percent"]:
        return tp, "ABAIXO DA FAIXA PREFERENCIAL"
    return tp, "FAIXA PREFERENCIAL"


def risk_reward(entry: float, stop: float, tp: float) -> float:
    risk = entry - stop
    if risk <= 0:
        return 0.0
    return (tp - entry) / risk


def position_size(balance: float, risk_pct: float, entry: float, stop: float) -> tuple[float, float]:
    """Returns (position_usd, capital_at_risk). Example: 1000,1%,100,95 -> (200,10)."""
    capital_risk = balance * risk_pct / 100
    stop_dist = (entry - stop) / entry
    if stop_dist <= 0:
        return 0.0, capital_risk
    return capital_risk / stop_dist, capital_risk
