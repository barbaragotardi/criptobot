"""Single-lever sweep on Dev (fast assets), parallel. Usage:
  poetry run python scripts/lever.py "invalidation.max_15m_candles_without_confirmation" 16 32 48 96
  poetry run python scripts/lever.py "risk.atr_multiplier" 0.5 0.75 1.0 1.5 [--base '{"k":"v"}']
"""

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
MIN_TRADES_OK = 10


def parse(v: str):
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("param")
    ap.add_argument("values", nargs="+")
    ap.add_argument("--base", default="{}", help="JSON baseline overrides")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    setup_logging("ERROR")
    base_cfg = load_config()
    baseline = json.loads(args.base)
    start_ms, end_ms = split_range("dev")
    for v in [parse(x) for x in args.values]:
        cfg = apply_overrides(base_cfg, {**baseline, args.param: v})
        trades = run_parallel(cfg, FAST_ASSETS, start_ms, end_ms, workers=args.workers)
        s = summarize(trades)
        flag = "" if s["trades"] >= MIN_TRADES_OK else "AMOSTRA INSUFICIENTE"
        print(f"{args.param}={v}: trades={s['trades']} win={s.get('win_rate')} "
              f"pf={s.get('profit_factor')} exp={s.get('expectancy_pct')} "
              f"rr_avg={s.get('rr_avg')} dd={s.get('max_drawdown_pct')} {flag}", flush=True)


if __name__ == "__main__":
    main()
