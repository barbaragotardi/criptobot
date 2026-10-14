"""Entry point: continuous loop with polling on new closed 15m candle."""

import logging
import threading
import time

import ccxt

from src.config import load_config, setup_logging
from src.strategy.cycle import run_cycle
from src.exchange.client import make_exchange, symbol_for
from src.paper.monitor import check_open_positions
from src.portfolio.listener import run_listener
from src.portfolio.monitor import check_portfolio_alerts
from src.strategy.state import connect_cfg

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
    conn = connect_cfg(cfg)
    exchange = make_exchange()
    log.info("robit starting (dry_run=%s)", cfg["system"].get("dry_run", True))
    if cfg.get("portfolio", {}).get("enabled", True):
        t = threading.Thread(target=run_listener, args=(cfg, None),
                             daemon=True, name="telegram-listener")
        t.start()
    if cfg.get("ai", {}).get("enabled") and cfg.get("ai", {}).get("rag", {}).get("enabled", True):
        t2 = threading.Thread(target=_news_ingest_loop, args=(cfg,),
                              daemon=True, name="news-ingest")
        t2.start()
    last_ts = None
    while True:
        last_ts = wait_for_new_candle(exchange, cfg, last_ts)
        log.info("New closed 15m candle, running cycle")
        try:
            results = run_cycle(cfg, conn, exchange)
            log.info("Cycle done: %s", results)
            try:
                closed = check_open_positions(conn, exchange, cfg)
                if closed:
                    log.info("Paper monitor closed: %s",
                             [(c["asset"], c["exit_reason"]) for c in closed])
            except Exception as e:
                log.error("Paper monitor failed: %s", e)
            try:
                alerts = check_portfolio_alerts(conn, exchange, cfg)
                if alerts:
                    log.info("Portfolio alerts: %s", alerts)
            except Exception as e:
                log.error("Portfolio monitor failed: %s", e)
        except Exception as e:
            log.error("Cycle failed: %s", e)
            time.sleep(60)


def _news_ingest_loop(cfg: dict) -> None:
    """Daemon: RSS -> news_articles every ingest_interval_min. Never raises."""
    import time
    interval = int(cfg.get("ai", {}).get("rag", {}).get("ingest_interval_min", 60)) * 60
    while True:
        try:
            conn = connect_cfg(cfg)
            try:
                from src.ai_agents.rag.store import ingest_once
                stats = ingest_once(conn, cfg)
                log.info("news ingest: %s", stats)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            log.warning("news ingest loop failed: %s", e)
        time.sleep(max(interval, 600))


if __name__ == "__main__":
    main()
