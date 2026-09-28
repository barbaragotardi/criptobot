"""Load config.yaml + .env. Fail loud on missing keys."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"


def load_config(path: str | Path = CONFIG_PATH) -> dict:
    load_dotenv(BASE_DIR / ".env")
    with open(path) as f:
        cfg = yaml.safe_load(f)
    cfg["telegram"] = {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    }
    return cfg
