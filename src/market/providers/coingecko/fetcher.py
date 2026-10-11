"""Fetch /coins/markets. Retry twice with exponential backoff, skip on failure."""

import logging
import time

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.coingecko.com/api/v3"
TIMEOUT = 10
BACKOFF = (1, 3)


def get_markets(ids: list[str], api_key: str = "", base_url: str = BASE_URL) -> bytes | None:
    """GET /coins/markets for the given CoinGecko ids. Returns raw bytes or None."""
    headers = {"User-Agent": "Mozilla/5.0 (robit market fetcher)"}
    if api_key:
        headers["x-cg-demo-api-key"] = api_key
    params = {
        "vs_currency": "usd",
        "ids": ",".join(ids),
        "order": "market_cap_desc",
        "sparkline": "false",
        "price_change_percentage": "24h",
    }
    last_exc = None
    for attempt in range(2):
        try:
            r = requests.get(f"{base_url}/coins/markets", headers=headers,
                             params=params, timeout=TIMEOUT)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            last_exc = e
            log.warning("CoinGecko failed (attempt %d): %s", attempt + 1, e)
            time.sleep(BACKOFF[attempt])
    log.error("CoinGecko skipped after 2 attempts: %s", last_exc)
    return None
