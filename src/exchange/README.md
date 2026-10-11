# Exchange

Wrapper ccxt/Binance, só dados públicos (`client.py`).

## Funções

- `make_exchange()` — ccxt.binance com `enableRateLimit`
- `symbol_for(asset, quote="USDT")` — `"BTC"` → `"BTC/USDT"`
- `fetch_ohlcv(exchange, symbol, timeframe, ...)` — OHLCV **só candles fechados**
- `fetch_warmup(...)` — histórico extra p/ aquecer EMAs
- `TF_MS` — `{"1d": ..., "4h": ..., "15m": ...}` em milissegundos

## Notas

- Só leitura: nenhuma ordem é executada
- Último candle (possivelmente aberto) sempre descartado
