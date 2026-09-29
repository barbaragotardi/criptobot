"""Run ONE candidate config on Validation (12 assets), exactly once per candidate."""

import argparse
import json
import sys

sys.path.insert(0, ".")

from src.backtest.metrics import breakdown, summarize
from src.backtest.parallel import run_parallel
from src.backtest.param_grid import apply_overrides
from src.backtest.splits import split_range
from src.config import load_config
from src.logging_config import setup_logging

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--overrides", required=True, help='JSON, e.g. {"risk.min_risk_reward": 1.0}')
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    setup_logging("ERROR")
    cfg = apply_overrides(load_config(), json.loads(args.overrides))
    start_ms, end_ms = split_range("validation")
    trades = run_parallel(cfg, cfg["assets"], start_ms, end_ms, workers=args.workers)
    print(f"\n== VALIDATION: {len(trades)} trades ==\n  overrides={args.overrides}")
    for k, v in summarize(trades).items():
        print(f"  {k}: {v}")
    for g, s in breakdown(trades, "asset").items():
        print(f"  {g}: trades={s['trades']} win_rate={s.get('win_rate')} pf={s.get('profit_factor')}")
