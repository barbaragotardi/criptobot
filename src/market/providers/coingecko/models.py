"""CoinGecko market snapshot model."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class MarketSnapshot:
    id: str
    symbol: str
    name: str
    current_price: float
    market_cap: int | None
    price_change_percentage_24h: float | None
    fetched_at: datetime
