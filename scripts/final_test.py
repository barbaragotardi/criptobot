"""Final test: runs the REGISTERED config on Test split (12 assets), once.

The config comes only from config/chosen_config.yaml (JSON overrides).
There is intentionally no CLI flag for free overrides: re-running Test with
tweaked params after seeing the result would invalidate the out-of-sample.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from src.backtest.metrics import breakdown, summarize
from src.backtest.parallel import run_parallel
from src.backtest.param_grid import apply_overrides
from src.backtest.splits import split_range
from src.config import load_config
from src.logging_config import setup_logging

CHOSEN_PATH = Path("config/chosen_config.yaml")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    if not CHOSEN_PATH.exists():
        sys.exit(f"refusing: {CHOSEN_PATH} does not exist. Register the final config first.")
    overrides = json.loads(CHOSEN_PATH.read_text() or "{}")
    setup_logging("ERROR")
    cfg = apply_overrides(load_config(), overrides)
    start_ms, end_ms = split_range("test")
    trades = run_parallel(cfg, cfg["assets"], start_ms, end_ms, workers=args.workers)
    print(f"\n== FINAL TEST: {len(trades)} trades ==\n  chosen={overrides}")
    for k, v in summarize(trades).items():
        print(f"  {k}: {v}")
    for by in ("asset", "year", "exit_reason"):
        print(f"-- by {by} --")
        for g, s in breakdown(trades, by).items():
            print(f"  {g}: trades={s['trades']} win_rate={s.get('win_rate')} pf={s.get('profit_factor')}")
