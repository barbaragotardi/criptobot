"""Parse /coins/markets JSON into MarketSnapshot. Stdlib only."""

import json
import logging
from datetime import datetime, timezone

from .models import MarketSnapshot

log = logging.getLogger(__name__)


def parse_markets(raw: bytes) -> list[MarketSnapshot]:
    """Parse markets JSON. Skips entries without id/symbol/current_price."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.error("CoinGecko JSON parse failed: %s", e)
        return []
    if not isinstance(data, list):
        log.error("CoinGecko unexpected payload: %s", type(data).__name__)
        return []
    now = datetime.now(timezone.utc)
    out: list[MarketSnapshot] = []
    for coin in data:
        if not isinstance(coin, dict):
            continue
        coin_id = coin.get("id")
        symbol = coin.get("symbol")
        price = coin.get("current_price")
        if not coin_id or not symbol or price is None:
            continue
        try:
            price = float(price)
        except (TypeError, ValueError):
            continue
        market_cap = coin.get("market_cap")
        try:
            market_cap = int(market_cap) if market_cap is not None else None
        except (TypeError, ValueError):
            market_cap = None
        change_24h = coin.get("price_change_percentage_24h")
        try:
            change_24h = float(change_24h) if change_24h is not None else None
        except (TypeError, ValueError):
            change_24h = None
        out.append(
            MarketSnapshot(
                id=coin_id,
                symbol=str(symbol).upper(),
                name=str(coin.get("name") or coin_id),
                current_price=price,
                market_cap=market_cap,
                price_change_percentage_24h=change_24h,
                fetched_at=now,
            )
        )
    return out
