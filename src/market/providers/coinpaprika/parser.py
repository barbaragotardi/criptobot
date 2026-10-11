"""Parse CoinPaprika JSON into models. Stdlib only."""

import json
import logging
from datetime import datetime, timezone

from .models import MarketDataPaprika

log = logging.getLogger(__name__)


def _float(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_coins(raw: bytes) -> list[dict]:
    """Parse /coins into [{id, symbol, is_active}]. Skips entries without id/symbol."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.error("CoinPaprika coins JSON parse failed: %s", e)
        return []
    if not isinstance(data, list):
        log.error("CoinPaprika coins unexpected payload: %s", type(data).__name__)
        return []
    out: list[dict] = []
    for coin in data:
        if not isinstance(coin, dict):
            continue
        coin_id = coin.get("id")
        symbol = coin.get("symbol")
        if not coin_id or not symbol:
            continue
        out.append({"id": coin_id, "symbol": symbol,
                    "is_active": bool(coin.get("is_active", False))})
    return out


def parse_ticker(raw: bytes) -> MarketDataPaprika | None:
    """Parse /tickers/{id}. None if missing id/symbol/price."""
    try:
        coin = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.error("CoinPaprika ticker JSON parse failed: %s", e)
        return None
    if not isinstance(coin, dict):
        log.error("CoinPaprika ticker unexpected payload: %s", type(coin).__name__)
        return None
    coin_id = coin.get("id")
    symbol = coin.get("symbol")
    quote = coin.get("quotes") or {}
    usd = quote.get("USD") or {}
    price = _float(usd.get("price"))
    if not coin_id or not symbol or price is None:
        return None
    return MarketDataPaprika(
        id=coin_id,
        symbol=str(symbol).upper(),
        name=str(coin.get("name") or symbol),
        price=price,
        market_cap=_int(usd.get("market_cap")),
        volume_24h=_float(usd.get("volume_24h")),
        volume_24h_change_24h=_float(usd.get("volume_24h_change_24h")),
        percent_change_15m=_float(usd.get("percent_change_15m")),
        percent_change_30m=_float(usd.get("percent_change_30m")),
        percent_change_1h=_float(usd.get("percent_change_1h")),
        percent_change_6h=_float(usd.get("percent_change_6h")),
        percent_change_12h=_float(usd.get("percent_change_12h")),
        percent_change_24h=_float(usd.get("percent_change_24h")),
        beta_value=_float(coin.get("beta_value")),
        total_supply=_float(coin.get("total_supply")),
        max_supply=_float(coin.get("max_supply")),
        fetched_at=datetime.now(timezone.utc),
    )
