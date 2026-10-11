"""Fetch CoinPaprika market data into memory."""

import logging

from .fetcher import BASE_URL, get_ticker
from .mapper import get_paprika_id
from .models import MarketDataPaprika
from .parser import parse_ticker

__all__ = ["MarketDataPaprika", "fetch_market_data"]

log = logging.getLogger(__name__)


def fetch_market_data(cfg: dict, assets: list[str] | None = None) -> list[MarketDataPaprika]:
    """Fetch /tickers for cfg assets via the mapper. Returns in-memory list; never raises."""
    assets = assets or cfg.get("assets", [])
    if not assets:
        return []
    paprika = cfg.get("coinpaprika", {})
    api_key = paprika.get("api_key", "")
    base_url = paprika.get("base_url", BASE_URL)
    out: list[MarketDataPaprika] = []
    for asset in assets:
        paprika_id = get_paprika_id(asset, api_key, base_url)
        if paprika_id is None:
            log.warning("CoinPaprika no mapping for %s, skipped", asset)
            continue
        raw = get_ticker(paprika_id, api_key, base_url)
        if raw is None:
            continue
        snapshot = parse_ticker(raw)
        if snapshot is None:
            log.warning("CoinPaprika parse failed for %s, skipped", asset)
            continue
        out.append(snapshot)
    return out
