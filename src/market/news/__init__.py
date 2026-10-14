"""Fetch + parse + classify crypto news into memory."""

from .cache import NewsCache
from .classifier import classify_all
from .fetcher import FEEDS, fetch_all
from .models import NewsArticle
from .parser import parse_all

__all__ = ["FEEDS", "NewsArticle", "NewsCache", "fetch_news"]


def fetch_news(feeds: dict[str, str | list[str]] | None = None, cfg: dict | None = None) -> list[NewsArticle]:
    """Full pipeline: fetch feeds, parse, classify, dedup. Returns in-memory list."""
    raw = fetch_all(feeds)
    articles = parse_all(raw)
    articles = classify_all(articles, cfg)
    cache = NewsCache()
    unique: list[NewsArticle] = []
    for a in articles:
        if not cache.is_duplicate(a.id):
            cache.add(a.id)
            unique.append(a)
    return unique
