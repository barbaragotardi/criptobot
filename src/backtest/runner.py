"""Replay 15m history through the production pipeline (evaluate_asset).

Per-asset with isolated state. KNOWN LIMITATION (V2a): exposure caps are
portfolio-level in production but apply per-asset here, so they rarely bind.
"""

import logging
import time

from src.backtest.clock import Replayer
from src.backtest.costs import apply_entry, apply_exit
from src.backtest.data_cache import load_cached
from src.backtest.exit_simulator import simulate_exit
from src.engine.cycle import evaluate_asset
from src.filters.filters import evaluate_market_filter
from src.setup.state import connect, get_state

log = logging.getLogger(__name__)
TF_15M_MS = 900_000


def run_asset(cfg: dict, asset: str, hist: dict, btc_hist: dict,
              start_ms: int = 0, end_ms: int = 0, log_every: int = 5000) -> list[dict]:
    cfg = dict(cfg)
    cfg["system"] = dict(cfg["system"], dry_run=True)  # never send real alerts in backtest
    conn = connect(":memory:")
    h15 = hist["15m"]
    rp, btc_rp = Replayer(hist, cfg), Replayer(btc_hist, cfg)
    trades: list[dict] = []
    t0 = time.time()
    for i in range(cfg["data"]["warmup"]["15m"], len(h15)):
        ts = int(h15.iloc[i]["ts"])
        if ts < start_ms or (end_ms and ts > end_ms):
            continue
        t_ms = ts + TF_15M_MS
        now_s = t_ms // 1000
        frames = rp.frames(t_ms)
        btc_1d = btc_rp.frames(t_ms, keys=("1D",))
        if frames is None or btc_1d is None:
            continue
        market_status = evaluate_market_filter(btc_1d["1D"], cfg)
        if log_every and i % log_every == 0:
            log.warning("%s replay %d/%d (%.0fs)", asset, i, len(h15), time.time() - t0)
        if evaluate_asset(asset, frames, market_status, conn, cfg, now_ts=now_s) != "SIGNAL":
            continue
        st = get_state(conn, asset)
        ex = simulate_exit(h15, i, st["stop"], st["tp"])
        entry_eff, exit_eff = apply_entry(st["entry"], cfg), apply_exit(ex["exit_price"], cfg)
        trades.append({
            "asset": asset,
            "open_ts": t_ms,
            "ema": st["ema"],
            "entry": entry_eff,
            "stop": st["stop"],
            "tp": st["tp"],
            "rr": st["rr"],
            "btc_bullish": market_status["bullish"],
            "exit_ts": int(h15.iloc[ex["exit_idx"]]["ts"]) + TF_15M_MS,
            "exit_price": exit_eff,
            "exit_reason": ex["reason"],
            "pnl_pct": (exit_eff - entry_eff) / entry_eff * 100,
        })
    conn.close()
    return trades


def run(cfg: dict, assets: list[str], start_ms: int = 0, end_ms: int = 0) -> list[dict]:
    base = cfg["backtest"]["data_dir"]
    btc_hist = {k: load_cached(base, cfg["market_filter"]["reference_asset"], k)
                for k in ("1D", "4H", "15m")}
    hist_cache = {"BTC": btc_hist}
    all_trades: list[dict] = []
    for asset in assets:
        hist = hist_cache.get(asset)
        if hist is None:
            hist = {k: load_cached(base, asset, k) for k in ("1D", "4H", "15m")}
        all_trades.extend(run_asset(cfg, asset, hist, btc_hist, start_ms, end_ms))
    return all_trades
