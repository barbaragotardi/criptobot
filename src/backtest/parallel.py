"""Parallel backtest across assets. Workers load their own parquet (no big IPC)."""

from concurrent.futures import ProcessPoolExecutor

from src.backtest.data_cache import load_cached
from src.backtest.runner import run_asset

KEYS = ("1D", "4H", "15m")


def _run_one(job: tuple) -> list[dict]:
    cfg, asset, start_ms, end_ms = job
    base = cfg["backtest"]["data_dir"]
    hist = {k: load_cached(base, asset, k) for k in KEYS}
    ref = cfg["market_filter"]["reference_asset"]
    btc_hist = hist if asset == ref else {k: load_cached(base, ref, k) for k in KEYS}
    return run_asset(cfg, asset, hist, btc_hist, start_ms, end_ms)


def run_parallel(cfg: dict, assets: list[str], start_ms: int = 0,
                 end_ms: int = 0, workers: int | None = None) -> list[dict]:
    with ProcessPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(_run_one, [(cfg, a, start_ms, end_ms) for a in assets]))
    return [t for rs in results for t in rs]
