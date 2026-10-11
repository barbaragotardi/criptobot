"""Ticker -> paprika_id mapping, loaded once into memory."""

import logging

from .fetcher import BASE_URL, get_coins
from .parser import parse_coins

log = logging.getLogger(__name__)

_TICKER_TO_ID: dict[str, str] = {}


def load_mapper(api_key: str = "", base_url: str = BASE_URL) -> dict[str, str]:
    """Fetch /coins once, cache {SYMBOL: paprika_id} for active coins. Returns mapping."""
    if _TICKER_TO_ID:
        return _TICKER_TO_ID
    raw = get_coins(api_key, base_url)
    if raw is None:
        return {}
    for coin in parse_coins(raw):
        symbol = coin["symbol"].upper()
        if coin["is_active"] and symbol not in _TICKER_TO_ID:
            _TICKER_TO_ID[symbol] = coin["id"]
    log.info("CoinPaprika mapper loaded: %d symbols", len(_TICKER_TO_ID))
    return _TICKER_TO_ID


def get_paprika_id(symbol: str, api_key: str = "",
                   base_url: str = BASE_URL) -> str | None:
    """Resolve SYMBOL to paprika_id, loading the mapper on first use."""
    return load_mapper(api_key, base_url).get(symbol.upper())
