"""Fetch CoinPaprika endpoints. Retry twice with backoff, skip on failure."""

import logging
import time

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.coinpaprika.com/v1"
TIMEOUT = 10
BACKOFF = (1, 3)


def _headers(api_key: str) -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (robit market fetcher)"}
    if api_key:
        headers["Authorization"] = api_key
    return headers


def _get(path: str, api_key: str, base_url: str) -> bytes | None:
    """GET one CoinPaprika endpoint with 2 attempts. Returns raw bytes or None."""
    last_exc = None
    for attempt in range(2):
        try:
            r = requests.get(f"{base_url}{path}", headers=_headers(api_key), timeout=TIMEOUT)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            last_exc = e
            log.warning("CoinPaprika %s failed (attempt %d): %s", path, attempt + 1, e)
            time.sleep(BACKOFF[attempt])
    log.error("CoinPaprika %s skipped after 2 attempts: %s", path, last_exc)
    return None


def get_coins(api_key: str = "", base_url: str = BASE_URL) -> bytes | None:
    """GET /coins for the ticker -> paprika_id mapping. Returns raw bytes or None."""
    return _get("/coins", api_key, base_url)


def get_ticker(paprika_id: str, api_key: str = "",
               base_url: str = BASE_URL) -> bytes | None:
    """GET /tickers/{paprika_id}. Returns raw bytes or None."""
    return _get(f"/tickers/{paprika_id}", api_key, base_url)
