"""Entry point: continuous loop with polling on new closed 15m candle."""

import logging
import time

import ccxt

from src.config import load_config
from src.engine.cycle import run_cycle
from src.exchange.client import make_exchange, symbol_for
from src.logging_config import setup_logging
from src.setup.state import connect

log = logging.getLogger(__name__)


def wait_for_new_candle(exchange, cfg, last_ts: int | None) -> int:
    """Poll until the latest closed 15m candle timestamp changes."""
    poll = cfg["system"].get("poll_seconds", 60)
    quote = cfg["system"]["quote_currency"]
    symbol = symbol_for("BTC", quote)
    tf = cfg["timeframe_map"]["15m"]
    while True:
        try:
            raw = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=2)
            latest_closed_ts = raw[-2][0] if len(raw) >= 2 else raw[-1][0]
            if last_ts is None or latest_closed_ts != last_ts:
                return latest_closed_ts
        except (ccxt.NetworkError, ccxt.ExchangeError) as e:
            log.warning("poll error: %s", e)
        time.sleep(poll)


def main() -> None:
    cfg = load_config()
    setup_logging()
    conn = connect(cfg["system"]["db_path"])
    exchange = make_exchange()
    log.info("robit starting (dry_run=%s)", cfg["system"].get("dry_run", True))
    last_ts = None
    while True:
        last_ts = wait_for_new_candle(exchange, cfg, last_ts)
        log.info("New closed 15m candle, running cycle")
        try:
            results = run_cycle(cfg, conn, exchange)
            log.info("Cycle done: %s", results)
        except Exception as e:
            log.error("Cycle failed: %s", e)
            time.sleep(60)


if __name__ == "__main__":
    main()
