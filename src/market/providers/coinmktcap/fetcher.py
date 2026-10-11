"""Fetch CoinMarketCap latest endpoints. Retry twice with backoff, skip on failure."""

import logging
import time

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://pro-api.coinmarketcap.com"
TIMEOUT = 10
BACKOFF = (1, 3)


def _get(path: str, params: dict, api_key: str, base_url: str) -> bytes | None:
    """GET one CMC endpoint with 2 attempts. Returns raw bytes or None."""
    headers = {
        "User-Agent": "Mozilla/5.0 (robit market fetcher)",
        "Accept": "application/json",
        "X-CMC_PRO_API_KEY": api_key,
    }
    last_exc = None
    for attempt in range(2):
        try:
            r = requests.get(f"{base_url}{path}", headers=headers,
                             params=params, timeout=TIMEOUT)
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            last_exc = e
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (402, 403):
                log.error("CoinMarketCap %s denied (HTTP %s): %s", path, status, e)
                return None
            log.warning("CoinMarketCap %s failed (attempt %d): %s", path, attempt + 1, e)
            time.sleep(BACKOFF[attempt])
    log.error("CoinMarketCap %s skipped after 2 attempts: %s", path, last_exc)
    return None


def get_global_metrics(api_key: str = "", base_url: str = BASE_URL) -> bytes | None:
    """GET /v1/global-metrics/quotes/latest. Returns raw bytes or None."""
    return _get("/v1/global-metrics/quotes/latest", {}, api_key, base_url)


def get_quotes(symbols: list[str], api_key: str = "",
               base_url: str = BASE_URL) -> bytes | None:
    """GET /v2/cryptocurrency/quotes/latest for symbols in one batch."""
    return _get("/v2/cryptocurrency/quotes/latest",
                {"symbol": ",".join(symbols)}, api_key, base_url)
