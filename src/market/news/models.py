"""Crypto news article model."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class NewsArticle:
    id: str
    source_name: str
    title: str
    summary: str
    url: str
    published_at: datetime
    category: str = "general"
    tags: list[str] = field(default_factory=list)
