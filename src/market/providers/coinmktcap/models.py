"""CoinMarketCap market data models."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class GlobalMetrics:
    btc_dominance: float
    eth_dominance: float
    active_cryptocurrencies: int
    total_market_cap_usd: int | None
    total_volume_24h_usd: int | None
    fetched_at: datetime


@dataclass
class MarketDataCMC:
    id: int
    symbol: str
    name: str
    price: float
    volume_24h: float | None
    percent_change_24h: float | None
    fetched_at: datetime
