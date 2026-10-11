# Config

Carregamento centralizado de config + logging.

## Módulos

- `loader.py` — `load_config(path)`: lê `config/config.yaml` + `.env`, retorna dict com chaves do projeto
- `logging.py` — `setup_logging(level)`: setup de logs com timestamps

## Uso

```python
from src.config import load_config, setup_logging

setup_logging("INFO")
cfg = load_config()
print(cfg["assets"])  # ['BTC', 'ETH', ...]
```

Re-exportado via `__init__.py`:
```python
from src.config import load_config, setup_logging
```

## Variáveis de ambiente

Via `.env` (veja `.env.example`):
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `COINGECKO_API_KEY` (opcional)
- `COINMKTCAP_API_KEY` (opcional)
- `COINPAPRIKA_API_KEY` (opcional)
