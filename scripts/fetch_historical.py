"""Download full historical OHLCV into data/historical/ parquet cache."""

import argparse
import sys

sys.path.insert(0, ".")

from src.backtest.data_cache import fetch_and_cache
from src.config import load_config
from src.logging_config import setup_logging

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", default="", help="comma-separated, default=all")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    setup_logging()
    cfg = load_config()
    assets = [a.strip() for a in args.assets.split(",") if a.strip()] or None
    fetch_and_cache(cfg, assets, refresh=args.refresh)
