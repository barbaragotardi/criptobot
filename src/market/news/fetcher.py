"""Fetch RSS feeds. Retry twice per source, skip on failure."""

import logging
import time

import requests

log = logging.getLogger(__name__)

FEEDS: dict[str, str | list[str]] = {
    "CoinTelegraph": ["https://cointelegraph.com/rss", "https://www.cointelegraph.com/rss"],
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "Bitcoin.com": "https://news.bitcoin.com/feed/",
    "CryptoPotato": "https://cryptopotato.com/feed/",
    "NewsBTC": "https://www.newsbtc.com/feed/",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (robit news fetcher)"}
TIMEOUT = 10


def fetch_feed(source_name: str, url: str | list[str]) -> bytes | None:
    """GET one feed with 2 attempts per URL. Falls back to next URL on failure."""
    urls = [url] if isinstance(url, str) else url
    last_exc = None
    for u in urls:
        for attempt in range(2):
            try:
                r = requests.get(u, headers=HEADERS, timeout=TIMEOUT)
                r.raise_for_status()
                return r.content
            except requests.RequestException as e:
                last_exc = e
                log.warning("RSS %s failed (%s, attempt %d): %s", source_name, u, attempt + 1, e)
                time.sleep(1 + attempt)
    log.error("RSS %s skipped after all URLs tried: %s", source_name, last_exc)
    return None


def fetch_all(feeds: dict[str, str | list[str]] | None = None) -> dict[str, bytes]:
    """Fetch all feeds. Failed sources are skipped, never raise."""
    feeds = feeds or FEEDS
    out: dict[str, bytes] = {}
    for name, url in feeds.items():
        raw = fetch_feed(name, url)
        if raw is not None:
            out[name] = raw
    return out
