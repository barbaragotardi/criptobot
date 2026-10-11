# Market Data

Fontes de dados externos: preços (`providers/`) e notícias (`news/`).

## Estrutura

- `providers/coingecko/` — `MarketSnapshot`, `fetch_market_data(cfg, assets)`
- `providers/coinmktcap/` — `GlobalMetrics`, `MarketDataCMC`, `fetch_market_data(cfg, assets)`, `fallback.fetch_with_fallback()`
- `providers/coinpaprika/` — `MarketDataPaprika` (variações 15m–24h, beta, supply), `fetch_market_data(cfg, assets)`
- `news/` — `fetch_news(feeds)` → `list[NewsArticle]` (fetch + parse + classify + dedup)

## Convenções

- Cada provider tem `models.py` + `fetcher.py` + `parser.py`, nunca levanta exceção.
- Novo provider: criar `providers/<nome>/` com o mesmo trio e expor `fetch_market_data` no `__init__.py` local.
