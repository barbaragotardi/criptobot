"""In-memory TTL cache for CoinMarketCap responses."""

import time


class Cache:
    """Store values with expiry. One instance per fetch session."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[object, float]] = {}

    def get(self, key: str) -> object | None:
        hit = self._store.get(key)
        if hit is None:
            return None
        value, expires_at = hit
        if time.time() >= expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: object, ttl_seconds: int) -> None:
        self._store[key] = (value, time.time() + ttl_seconds)

    def __len__(self) -> int:
        return len(self._store)
