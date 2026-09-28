"""Exit simulation on 15m candles. Same-candle stop+TP touch -> STOP (conservative)."""

import pandas as pd


def simulate_exit(df_15m: pd.DataFrame, entry_idx: int, stop: float, tp: float) -> dict:
    """Walk candles AFTER entry_idx. Returns {exit_idx, exit_price, reason}."""
    for i in range(entry_idx + 1, len(df_15m)):
        row = df_15m.iloc[i]
        stop_hit = row["low"] <= stop
        tp_hit = row["high"] >= tp
        if stop_hit:
            return {"exit_idx": i, "exit_price": stop, "reason": "STOP"}
        if tp_hit:
            return {"exit_idx": i, "exit_price": tp, "reason": "TP"}
    last = df_15m.iloc[-1]
    return {"exit_idx": len(df_15m) - 1, "exit_price": float(last["close"]), "reason": "OPEN_AT_END"}
