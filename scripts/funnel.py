"""Funnel quantification on Dev (fast assets). Counts statuses + rejection reasons."""

import argparse
import logging
import sys
from collections import Counter

sys.path.insert(0, ".")

from src.backtest.data_cache import load_cached
from src.backtest.runner import run_asset
from src.backtest.splits import split_range
from src.config import load_config
from src.logging_config import setup_logging


class ReasonCounter(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.INFO)
        self.reasons = Counter()

    def emit(self, record):
        msg = record.getMessage()
        if "SIGNAL REJECTED" in msg:
            if "absolute minimum" in msg:
                self.reasons["reject_return"] += 1
            elif "R/R" in msg:
                self.reasons["reject_rr"] += 1
            elif "exposure" in msg:
                self.reasons["reject_exposure"] += 1
            else:
                self.reasons["reject_other"] += 1
        elif "15m confirmation: PASS" in msg:
            self.reasons["confirm_pass"] += 1
        elif "touch detected" in msg and "4H EMA" in msg:
            self.reasons["touch"] += 1


FAST_ASSETS = ["BTC", "ETH", "XRP", "SOL"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/funnel_dev.txt")
    ap.add_argument("--overrides", default="{}", help="JSON dotted overrides")
    args = ap.parse_args()
    setup_logging("INFO")
    handler = ReasonCounter()
    logging.getLogger().addHandler(handler)
    import json
    from src.backtest.param_grid import apply_overrides
    cfg = apply_overrides(load_config(), json.loads(args.overrides))
    cfg["system"] = dict(cfg["system"], dry_run=True)
    start_ms, end_ms = split_range("dev")
    base = cfg["backtest"]["data_dir"]
    ref = cfg["market_filter"]["reference_asset"]
    btc_hist = {k: load_cached(base, ref, k) for k in ("1D", "4H", "15m")}
    lines = []
    total_status = Counter()
    for asset in FAST_ASSETS:
        hist = btc_hist if asset == ref else {k: load_cached(base, asset, k) for k in ("1D", "4H", "15m")}
        before = dict(handler.reasons)
        counter: Counter = Counter()
        run_asset(cfg, asset, hist, btc_hist, start_ms, end_ms, status_counter=counter)
        total_status.update(counter)
        delta = {k: handler.reasons[k] - before.get(k, 0) for k in handler.reasons if handler.reasons[k] - before.get(k, 0)}
        lines.append(f"{asset}: statuses={dict(counter)} reasons={delta}")
    lines.append(f"TOTAL statuses={dict(total_status)}")
    lines.append(f"TOTAL reasons={dict(handler.reasons)}")
    Path_out = args.out
    with open(Path_out, "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
