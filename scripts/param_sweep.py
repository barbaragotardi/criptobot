"""Grid search on Dev split (fast assets), parallel. Flags thin samples explicitly."""

import argparse
import csv
import sys

sys.path.insert(0, ".")

from src.backtest.metrics import summarize
from src.backtest.parallel import run_parallel
from src.backtest.param_grid import apply_overrides, expand
from src.backtest.splits import split_range
from src.config import load_config
from src.logging_config import setup_logging

FAST_ASSETS = ["BTC", "ETH", "XRP", "SOL"]
MIN_TRADES_OK = 10

GRID = {
    "risk.min_risk_reward": [1.0, 1.5, 2.0],
    "entry.touch_threshold_percent": [1.0, 2.0],
    "risk.stop_method": ["structure_atr", "atr_only"],
    "confirmation.method": ["reversal", "ema_reclaim"],
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/sweep_dev.csv")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    setup_logging("ERROR")
    base = load_config()
    start_ms, end_ms = split_range("dev")
    rows = []
    combos = expand(GRID)
    print(f"{len(combos)} combos x {FAST_ASSETS} (dev), workers={args.workers}", flush=True)
    for n, ov in enumerate(combos):
        cfg = apply_overrides(base, ov)
        trades = run_parallel(cfg, FAST_ASSETS, start_ms, end_ms, workers=args.workers)
        s = summarize(trades)
        flag = "" if s["trades"] >= MIN_TRADES_OK else "AMOSTRA INSUFICIENTE"
        row = {**{k: str(v) for k, v in ov.items()}, **{k: s.get(k, "") for k in
               ("trades", "win_rate", "profit_factor", "expectancy_pct", "max_drawdown_pct")}, "flag": flag}
        rows.append(row)
        print(f"[{n+1}/{len(combos)}] {ov} -> trades={s['trades']} exp={s.get('expectancy_pct')} {flag}", flush=True)
    rows.sort(key=lambda r: (r["flag"] == "", float(r["expectancy_pct"] or -1e9)), reverse=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
