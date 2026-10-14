# News

Fetch + parse + classify de notícias crypto via RSS, em memória (`__init__.py`).

## Pipeline

- `fetch_news(feeds=None)` — fetch → parse → classify → dedup, retorna `list[NewsArticle]`
- Ordem: `fetcher.fetch_all` → `parser.parse_all` → `classifier.classify_all` → `NewsCache` dedup

## Arquivos

- `models.py` — `NewsArticle` (`id`, `source_name`, `title`, `summary`, `url`, `published_at`, `category`, `tags`)
- `fetcher.py` — `FEEDS`, `fetch_feed(source, url)`, `fetch_all(feeds=None)` via `requests`
- `parser.py` — `clean_html`, `parse_date`, `parse_feed(source, raw)`, `parse_all(raw_feeds)` (só stdlib)
- `classifier.py` — `classify(article)`, `classify_all(articles)` por keywords
- `cache.py` — `NewsCache` (`is_duplicate`, `add`); uma instância por chamada, sem persistência

## Fontes (`FEEDS`)

- CoinTelegraph (2 URLs, fallback), CoinDesk, Bitcoin.com, CryptoPotato, NewsBTC

## Classificação

- `macro` — SEC, Fed, ETF, inflação, regulação… (`MACRO_KEYWORDS`)
- `coin_specific` — BTC, ETH, SOL… (`COIN_KEYWORDS`)
- `macro_and_coin` — ambos; `general` — nenhum
- Tickers curtos (`BTC`, `SOL`, `LINK`…) exigem word boundary; nomes cheios usam substring

## Notas

- Nunca levanta: fonte com falha é pulada (`fetch_all`), XML inválido retorna `[]` (`parse_feed`)
- `fetch_feed`: 2 tentativas por URL, `timeout=10s`, `sleep(1+attempt)` entre retries
- `id = sha1(link)[:16]`; itens sem título/link ou sem data parseável são descartados
- `parse_all` ordena por `published_at` desc; datas normalizadas p/ UTC aware
- Standalone: nenhum caller no pipeline de trade hoje, sem config em `config.yaml`, sem tabelas
