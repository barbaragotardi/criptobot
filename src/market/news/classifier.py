"""Classify news as macro / coin_specific / macro_and_coin / general."""

import re

from .models import NewsArticle

MACRO_KEYWORDS = [
    "SEC", "Fed", "Federal Reserve", "Treasury", "Gary Gensler", "CBDC",
    "Regulation", "Lawsuit", "Congress", "MiCA", "Taxes",
    "Inflation", "CPI", "Interest Rates", "Bonds", "Wall Street", "ETF",
    "Bull Market", "Bear Market", "Macro", "Global Market",
]

COIN_KEYWORDS = [
    "Bitcoin", "BTC", "Ethereum", "ETH", "Solana", "SOL",
    "Cardano", "ADA", "Ripple", "XRP", "Polkadot", "DOT",
    "Chainlink", "LINK", "Binance", "BNB", "Dogecoin", "DOGE",
]

# Short tickers collide with common words via substring ("SOL" in "sold",
# "LINK" in "linked"), so they require word boundaries. Full names keep
# plain substring matching.
TICKERS = {"BTC", "ETH", "SOL", "ADA", "XRP", "DOT", "LINK", "BNB", "DOGE"}


def _contains(text_lower: str, keyword: str) -> bool:
    if keyword in TICKERS:
        return re.search(r"\b" + re.escape(keyword.lower()) + r"\b", text_lower) is not None
    return keyword.lower() in text_lower


def classify(article: NewsArticle) -> NewsArticle:
    """Mutate article in place with category + tags. Case-insensitive."""
    text = f"{article.title} {article.summary}"
    lowered = text.lower()
    macro_tags = [k for k in MACRO_KEYWORDS if k.lower() in lowered]
    coin_tags = [k for k in COIN_KEYWORDS if _contains(lowered, k)]
    article.tags = macro_tags + coin_tags
    if macro_tags and coin_tags:
        article.category = "macro_and_coin"
    elif macro_tags:
        article.category = "macro"
    elif coin_tags:
        article.category = "coin_specific"
    else:
        article.category = "general"
    return article


def classify_all(articles: list[NewsArticle]) -> list[NewsArticle]:
    return [classify(a) for a in articles]
