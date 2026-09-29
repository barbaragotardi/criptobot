"""One-at-a-time sensitivity around a baseline (Dev, fast assets)."""

import argparse
import json
import sys

sys.path.insert(0, ".")

from src.backtest.metrics import summarize
from src.backtest.parallel import run_parallel
from src.backtest.param_grid import apply_overrides
from src.backtest.splits import split_range
from src.config import load_config
from src.logging_config import setup_logging

FAST_ASSETS = ["BTC", "ETH", "XRP", "SOL"]

OAT = {
    "risk.min_risk_reward": [1.0, 1.5, 2.0, 2.5],
    "entry.touch_threshold_percent": [0.5, 1.0, 2.0, 3.0],
    "risk.atr_multiplier": [0.5, 1.0, 1.5, 2.0],
    "target.absolute_min_percent": [0.0, 3.0, 5.0],
}


def metric_of(cfg, start_ms, end_ms, workers):
    s = summarize(run_parallel(cfg, FAST_ASSETS, start_ms, end_ms, workers=workers))
    return s


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default="{}", help="JSON overrides of chosen config")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    setup_logging("ERROR")
    base = load_config()
    baseline_ov = json.loads(args.baseline)
    start_ms, end_ms = split_range("dev")
    base_s = metric_of(apply_overrides(base, baseline_ov), start_ms, end_ms, args.workers)
    base_exp = base_s.get("expectancy_pct", 0) or 0
    print(f"BASELINE {baseline_ov} -> trades={base_s['trades']} exp={base_exp}")
    for param, values in OAT.items():
        for v in values:
            ov = {**baseline_ov, param: v}
            s = metric_of(apply_overrides(base, ov), start_ms, end_ms, args.workers)
            exp = s.get("expectancy_pct", 0) or 0
            is_base = " <== baseline" if ov == baseline_ov else ""
            print(f"  {param}={v}: trades={s['trades']} exp={exp} "
                  f"delta={round(exp - base_exp, 2)}{is_base}", flush=True)
