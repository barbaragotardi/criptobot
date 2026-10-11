"""CoinGecko-first market data with CoinMarketCap fallback. Never raises."""

import logging

from src.market.providers.coingecko import MarketSnapshot, fetch_market_data as fetch_coingecko

from . import GlobalMetrics, MarketDataCMC, fetch_market_data as fetch_coinmktcap

log = logging.getLogger(__name__)


def fetch_with_fallback(
    cfg: dict,
    assets: list[str] | None = None,
    force_source: str | None = None,
) -> tuple[list[MarketSnapshot] | None, GlobalMetrics | None, list[MarketDataCMC] | None]:
    """Fetch CoinGecko, fall back to CoinMarketCap. Returns (cg, cmc_global, cmc_quotes)."""
    assets = assets or cfg.get("assets", [])
    if not assets:
        return None, None, None

    if force_source == "coinmktcap":
        global_metrics, quotes = fetch_coinmktcap(cfg, assets)
        return None, global_metrics, quotes

    if force_source == "coingecko":
        return fetch_coingecko(cfg, assets), None, None

    snapshots = fetch_coingecko(cfg, assets)
    if snapshots:
        log.info("Market data from CoinGecko: %d assets", len(snapshots))
        return snapshots, None, None

    log.error("CoinGecko fetch failed, trying CoinMarketCap as fallback")
    global_metrics, quotes = fetch_coinmktcap(cfg, assets)
    if global_metrics is not None or quotes:
        log.error("Using CoinMarketCap as fallback source")
        return None, global_metrics, quotes

    log.error("Both CoinGecko and CoinMarketCap fetch failed")
    return None, None, None
