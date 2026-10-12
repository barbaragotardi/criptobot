"""Parse CoinMarketCap JSON into models. Stdlib only."""

import json
import logging
from datetime import datetime, timezone

from .models import GlobalMetrics, MarketDataCMC

log = logging.getLogger(__name__)


def _payload(raw: bytes) -> dict | None:
    """Decode JSON and reject non-zero status.error_code. None on failure."""
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        log.error("CoinMarketCap JSON parse failed: %s", e)
        return None
    if not isinstance(payload, dict):
        log.error("CoinMarketCap unexpected payload: %s", type(payload).__name__)
        return None
    status = payload.get("status") or {}
    if status.get("error_code", 0) != 0:
        log.error("CoinMarketCap API error %s: %s",
                  status.get("error_code"), status.get("error_message"))
        return None
    return payload


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


def parse_global(raw: bytes) -> GlobalMetrics | None:
    """Parse /v1/global-metrics/quotes/latest. None if invalid."""
    payload = _payload(raw)
    if payload is None:
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        log.error("CoinMarketCap global missing data object")
        return None
    btc_dom = _float(data.get("btc_dominance"))
    eth_dom = _float(data.get("eth_dominance"))
    active = _int(data.get("active_cryptocurrencies"))
    if btc_dom is None or eth_dom is None or active is None:
        log.error("CoinMarketCap global missing dominance/cryptocurrency fields")
        return None
    quote = data.get("quote") or {}
    usd = quote.get("USD") or {}
    return GlobalMetrics(
        btc_dominance=btc_dom,
        eth_dominance=eth_dom,
        active_cryptocurrencies=active,
        total_market_cap_usd=_int(usd.get("total_market_cap")),
        total_volume_24h_usd=_int(usd.get("total_volume_24h")),
        fetched_at=datetime.now(timezone.utc),
    )


def parse_quotes(raw: bytes) -> list[MarketDataCMC]:
    """Parse /v2/cryptocurrency/quotes/latest. Skips entries without id/symbol/price."""
    payload = _payload(raw)
    if payload is None:
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        log.error("CoinMarketCap quotes missing data object")
        return []
    now = datetime.now(timezone.utc)
    out: list[MarketDataCMC] = []
    for symbol, entry in data.items():
        # /v2/quotes/latest?symbol=BTC retorna {"BTC": [{...}]} (lista por symbol)
        if isinstance(entry, list):
            if not entry:
                continue
            entry = entry[0]
        if not isinstance(entry, dict):
            continue
        coin_id = _int(entry.get("id"))
        quote = entry.get("quote") or {}
        usd = quote.get("USD") or {}
        price = _float(usd.get("price"))
        if coin_id is None or not symbol or price is None:
            continue
        out.append(
            MarketDataCMC(
                id=coin_id,
                symbol=str(entry.get("symbol") or symbol).upper(),
                name=str(entry.get("name") or symbol),
                price=price,
                volume_24h=_float(usd.get("volume_24h")),
                percent_change_24h=_float(usd.get("percent_change_24h")),
                fetched_at=now,
            )
        )
    return out
