"""Fetch CoinMarketCap market data into memory, with TTL cache."""

from .cache import Cache
from .fetcher import BASE_URL, get_global_metrics, get_quotes
from .models import GlobalMetrics, MarketDataCMC
from .parser import parse_global, parse_quotes

__all__ = ["Cache", "GlobalMetrics", "MarketDataCMC", "fetch_market_data"]

DEFAULT_TTL = 3600

_CACHE = Cache()


def fetch_market_data(cfg: dict, assets: list[str] | None = None,
                      use_cache: bool = True) -> tuple[GlobalMetrics | None, list[MarketDataCMC]]:
    """Fetch global metrics + batched quotes. Returns (global, quotes); never raises."""
    assets = assets or cfg.get("assets", [])
    if not assets:
        return None, []
    cmc = cfg.get("coinmktcap", {})
    api_key = cmc.get("api_key", "")
    base_url = cmc.get("base_url", BASE_URL)
    ttl = cmc.get("cache_ttl_seconds", DEFAULT_TTL)
    symbols = sorted(a.upper() for a in assets)

    if use_cache:
        cached_global = _CACHE.get("global")
        cached_quotes = _CACHE.get("quotes:" + ",".join(symbols))
        if cached_global is not None and cached_quotes is not None:
            return cached_global, cached_quotes  # type: ignore[return-value]

    raw_global = get_global_metrics(api_key, base_url)
    global_metrics = parse_global(raw_global) if raw_global is not None else None

    raw_quotes = get_quotes(symbols, api_key, base_url)
    quotes = parse_quotes(raw_quotes) if raw_quotes is not None else []

    if use_cache:
        if global_metrics is not None:
            _CACHE.set("global", global_metrics, ttl)
        if quotes:
            _CACHE.set("quotes:" + ",".join(symbols), quotes, ttl)
    return global_metrics, quotes
