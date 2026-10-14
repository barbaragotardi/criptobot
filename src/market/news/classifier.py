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
    "Bitcoin", "BTC", "Ethereum", "ETH", "Ripple", "XRP", "Solana", "SOL",
    "Chainlink", "LINK", "Stellar", "XLM", "Bitcoin Cash", "BCH",
    "NEAR Protocol", "NEAR", "Uniswap", "UNI", "Litecoin", "LTC",
    "Avalanche", "AVAX", "Aave", "AAVE", "Quant", "QNT", "Cosmos", "ATOM",
    "Cardano", "ADA", "Hedera", "HBAR", "Polkadot", "DOT",
    "Ethereum Classic", "ETC", "Polygon", "POL", "Algorand", "ALGO",
    "Arbitrum", "ARB", "Celestia", "TIA", "Tezos", "XTZ", "Immutable", "IMX",
    "The Graph", "GRT", "Optimism", "OP", "Lido", "LDO",
]

# Short tickers collide with common words via substring ("SOL" in "sold",
# "LINK" in "linked"), so they require word boundaries. Full names keep
# plain substring matching.
TICKERS = {"BTC", "ETH", "XRP", "SOL", "LINK", "XLM", "BCH", "NEAR", "UNI",
           "LTC", "AVAX", "AAVE", "QNT", "ATOM", "ADA", "HBAR", "DOT", "ETC",
           "POL", "ALGO", "ARB", "TIA", "XTZ", "IMX", "GRT", "OP", "LDO"}


def _coin_keywords(cfg: dict | None) -> tuple[list[str], set[str]]:
    """Build (keywords, tickers) from cfg assets + ai.asset_aliases.

    Falls back to module-level COIN_KEYWORDS/TICKERS when cfg is None
    or carries no usable assets (keeps standalone use working).
    """
    if not cfg:
        return COIN_KEYWORDS, TICKERS
    assets = cfg.get("assets", []) or []
    if not assets:
        return COIN_KEYWORDS, TICKERS
    aliases = (cfg.get("ai", {}).get("asset_aliases", {}) or {})
    keywords: list[str] = []
    for asset in assets:
        names = aliases.get(asset, [asset])
        for name in names:
            name = str(name)
            if name not in keywords:
                keywords.append(name)
    if not keywords:
        return COIN_KEYWORDS, TICKERS
    return keywords, {str(a).upper() for a in assets}


def _contains(text_lower: str, keyword: str, tickers: set[str] | None = None) -> bool:
    tickers = TICKERS if tickers is None else tickers
    if keyword in tickers or keyword.upper() in tickers:
        return re.search(r"\b" + re.escape(keyword.lower()) + r"\b", text_lower) is not None
    return keyword.lower() in text_lower


def classify(article: NewsArticle, cfg: dict | None = None) -> NewsArticle:
    """Mutate article in place with category + tags. Case-insensitive."""
    text = f"{article.title} {article.summary}"
    lowered = text.lower()
    macro_tags = [k for k in MACRO_KEYWORDS if k.lower() in lowered]
    coin_keywords, tickers = _coin_keywords(cfg)
    coin_tags = [k for k in coin_keywords if _contains(lowered, k, tickers)]
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


def classify_all(articles: list[NewsArticle], cfg: dict | None = None) -> list[NewsArticle]:
    return [classify(a, cfg) for a in articles]
