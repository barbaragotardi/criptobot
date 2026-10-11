"""Fetch CoinGecko market data into memory."""

from .fetcher import BASE_URL, get_markets
from .models import MarketSnapshot
from .parser import parse_markets

__all__ = ["MarketSnapshot", "fetch_market_data"]

SYMBOL_TO_ID = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "XRP": "ripple",
    "SOL": "solana",
    "LINK": "chainlink",
    "XLM": "stellar",
    "BCH": "bitcoin-cash",
    "NEAR": "near",
    "UNI": "uniswap",
    "LTC": "litecoin",
    "AVAX": "avalanche-2",
}


def fetch_market_data(cfg: dict, assets: list[str] | None = None) -> list[MarketSnapshot]:
    """Full pipeline: fetch /coins/markets for cfg assets, parse, return in-memory list."""
    assets = assets or cfg.get("assets", [])
    if not assets:
        return []
    ids = [SYMBOL_TO_ID.get(a, a.lower()) for a in assets]
    coingecko = cfg.get("coingecko", {})
    raw = get_markets(ids,
                      api_key=coingecko.get("api_key", ""),
                      base_url=coingecko.get("base_url", BASE_URL))
    if raw is None:
        return []
    return parse_markets(raw)
