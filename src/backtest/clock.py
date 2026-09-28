"""As-of slicing: what would production have seen at candle time `t`?

Production calls fetch_warmup (last N closed candles) then add_indicators.
Backtest replicates that by slicing cached history to closed candles only,
then running the SAME indicator functions on the SAME window size.
"""

import pandas as pd

from src.exchange.client import TF_MS
from src.indicators.engine import add_indicators


import numpy as np
import pandas as pd

from src.exchange.client import TF_MS
from src.indicators.engine import add_indicators


def frames_at(hist: dict[str, pd.DataFrame], t_ms: int, cfg: dict) -> dict[str, pd.DataFrame] | None:
    """`t_ms`: close time of the current 15m candle. Returns None until all TFs have warmup rows."""
    out: dict[str, pd.DataFrame] = {}
    for key in ("1D", "4H", "15m"):
        tf = cfg["timeframe_map"][key]
        vis = hist[key][hist[key]["ts"] <= t_ms - TF_MS[tf]]
        need = cfg["data"]["warmup"][key]
        if len(vis) < need:
            return None
        window = vis.iloc[-need:].reset_index(drop=True)
        out[key] = add_indicators(window, cfg["ema"]["periods"], cfg["atr"]["period"])
    return out


class Replayer:
    """Stateful cursor over cached history. Same windows as frames_at, but
    recomputes a TF's indicators only when a new candle closed in that TF."""

    def __init__(self, hist: dict[str, pd.DataFrame], cfg: dict):
        self.hist = hist
        self.cfg = cfg
        self.ts = {k: hist[k]["ts"].to_numpy() for k in ("1D", "4H", "15m")}
        self.cache: dict[str, tuple[int, pd.DataFrame]] = {}

    def frames(self, t_ms: int, keys: tuple[str, ...] = ("1D", "4H", "15m")) -> dict[str, pd.DataFrame] | None:
        out: dict[str, pd.DataFrame] = {}
        for key in keys:
            tf = self.cfg["timeframe_map"][key]
            count = int(np.searchsorted(self.ts[key], t_ms - TF_MS[tf], side="right"))
            need = self.cfg["data"]["warmup"][key]
            if count < need:
                return None
            cached = self.cache.get(key)
            if cached is not None and cached[0] == count:
                out[key] = cached[1]
            else:
                window = self.hist[key].iloc[count - need:count].reset_index(drop=True)
                frame = add_indicators(window, self.cfg["ema"]["periods"], self.cfg["atr"]["period"])
                self.cache[key] = (count, frame)
                out[key] = frame
        return out
