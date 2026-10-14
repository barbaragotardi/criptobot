"""Council orchestration: background submit, parallel news+risk, join chief."""

import concurrent.futures
import json
import logging
import threading
import time

log = logging.getLogger(__name__)
_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="council")
_LOCK = threading.Lock()


def _save_report(conn, asset: str, setup: dict, news, risk, briefing,
                 model: str, ok: bool, error: str = "") -> None:
    try:
        conn.execute(
            "INSERT INTO council_reports (asset, ts, setup_json, news_json, risk_json,"
            " briefing_json, model, ok, error) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (asset, int(time.time() * 1000), json.dumps(setup, default=str)[:4000],
             (news.model_dump_json() if news else "{}")[:4000],
             (risk.model_dump_json() if risk else "{}")[:4000],
             (briefing.model_dump_json() if briefing else "{}")[:4000],
             model, int(bool(ok)), (error or "")[:500]))
        conn.commit()
    except Exception as e:
        log.warning("council report save failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass


def run_council(asset: str, cfg: dict, conn) -> dict | None:
    """Synchronous council. Returns briefing dict or None. Never raises."""
    from src.ai_agents import agents
    from src.ai_agents.context import facts_text, portfolio_facts, setup_facts
    from src.ai_agents.llm import enabled
    from src.ai_agents.rag.retrieve import retrieve

    if not enabled(cfg):
        return None
    model = cfg.get("ai", {}).get("model", "")
    setup = setup_facts(conn, asset)
    pf = portfolio_facts(conn, asset, cfg)
    try:
        snippets, mode = retrieve(conn, cfg, asset)
    except Exception as e:
        log.warning("council retrieve failed: %s", e)
        snippets, mode = [], "sql"
    setup["news_mode"] = mode
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            fn = ex.submit(agents.run_news, conn, cfg, snippets)
            fr = ex.submit(agents.run_risk, conn, cfg, facts_text(setup, pf))
            news = fn.result()
            risk = fr.result()
        briefing = agents.run_chief(conn, cfg, news, risk, asset, str(setup.get("state")))
        _save_report(conn, asset, setup, news, risk, briefing, model, True)
        return {"asset": asset, "news": news.model_dump(),
                "risk": risk.model_dump(), "briefing": briefing.model_dump(),
                "setup": setup}
    except Exception as e:
        log.warning("council failed for %s: %s", asset, e)
        _save_report(conn, asset, setup, None, None, None, model, False, str(e))
        return None


def submit(asset: str, cfg: dict) -> None:
    """Fire-and-forget from run_cycle: own DB connection, sends follow-up Telegram."""
    from src.ai_agents.llm import enabled

    if not enabled(cfg):
        return

    def _job():
        conn = None
        try:
            from src.strategy.state import connect_cfg
            conn = connect_cfg(cfg)
            with _LOCK:  # serialize LLM spend; signals are rare
                res = run_council(asset, cfg, conn)
            if not res:
                return
            from src.alerts.telegram import format_council, send_telegram
            tg = cfg["telegram"]
            text = format_council(res)
            send_telegram(tg["bot_token"], tg["chat_id"], text,
                          dry_run=cfg["system"].get("dry_run", True))
        except Exception as e:
            log.warning("council background failed for %s: %s", asset, e)
        finally:
            try:
                if conn:
                    conn.close()
            except Exception:
                pass

    _POOL.submit(_job)
