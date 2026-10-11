"""Load config.yaml + .env. Fail loud on missing keys."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"


def load_config(path: str | Path = CONFIG_PATH) -> dict:
    load_dotenv(BASE_DIR / ".env")
    with open(path) as f:
        cfg = yaml.safe_load(f)
    cfg["telegram"] = {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    }
    cfg["coingecko"] = {
        "api_key": os.getenv("COINGECKO_API_KEY", ""),
        "base_url": "https://api.coingecko.com/api/v3",
    }
    cfg["coinmktcap"] = {
        "api_key": os.getenv("COINMKTCAP_API_KEY", ""),
        "base_url": "https://pro-api.coinmarketcap.com",
        "cache_ttl_seconds": 3600,
    }
    cfg["coinpaprika"] = {
        "api_key": os.getenv("COINPAPRIKA_API_KEY", ""),
        "base_url": "https://api.coinpaprika.com/v1",
    }
    return cfg
