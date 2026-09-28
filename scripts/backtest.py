"""Backtest CLI: replay history, print metrics report."""

import argparse
import datetime
import json
import sys

sys.path.insert(0, ".")

from src.backtest.metrics import breakdown, summarize
from src.backtest.runner import run
from src.config import load_config
from src.logging_config import setup_logging


def to_ms(s: str) -> int:
    if not s:
        return 0
    dt = datetime.datetime.fromisoformat(s).replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp() * 1000)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", default="", help="comma-separated, default=all")
    ap.add_argument("--start", default="", help="YYYY-MM-DD")
    ap.add_argument("--end", default="", help="YYYY-MM-DD")
    ap.add_argument("--save", default="", help="save trades json to path")
    args = ap.parse_args()
    setup_logging("WARNING")
    cfg = load_config()
    assets = [a.strip() for a in args.assets.split(",") if a.strip()] or cfg["assets"]
    trades = run(cfg, assets, to_ms(args.start), to_ms(args.end))
    if args.save:
        with open(args.save, "w") as f:
            json.dump(trades, f)
    print(f"\n== BACKTEST: {len(trades)} trades ==")
    for k, v in summarize(trades).items():
        print(f"  {k}: {v}")
    for by in ("asset", "year", "exit_reason"):
        print(f"\n-- by {by} --")
        for g, s in breakdown(trades, by).items():
            print(f"  {g}: trades={s['trades']} win_rate={s.get('win_rate')} pf={s.get('profit_factor')}")
