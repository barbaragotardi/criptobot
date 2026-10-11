"""CoinPaprika market data model."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class MarketDataPaprika:
    id: str
    symbol: str
    name: str
    price: float
    market_cap: int | None
    volume_24h: float | None
    volume_24h_change_24h: float | None
    percent_change_15m: float | None
    percent_change_30m: float | None
    percent_change_1h: float | None
    percent_change_6h: float | None
    percent_change_12h: float | None
    percent_change_24h: float | None
    beta_value: float | None
    total_supply: float | None
    max_supply: float | None
    fetched_at: datetime
