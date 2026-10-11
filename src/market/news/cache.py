"""In-memory dedup cache for fetched news."""

import logging

log = logging.getLogger(__name__)


class NewsCache:
    """Store seen article ids. One instance per fetch session."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def is_duplicate(self, article_id: str) -> bool:
        return article_id in self._seen

    def add(self, article_id: str) -> None:
        self._seen.add(article_id)

    def __len__(self) -> int:
        return len(self._seen)
