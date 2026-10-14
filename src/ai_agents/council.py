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
                  model: str, ok: bool, error: str = "", trace_id: str = "") -> None:
    try:
        conn.execute(
            "INSERT INTO council_reports (asset, ts, setup_json, news_json, risk_json,"
            " briefing_json, model, ok, error, trace_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (asset, int(time.time() * 1000), json.dumps(setup, default=str)[:4000],
             (news.model_dump_json() if news else "{}")[:4000],
             (risk.model_dump_json() if risk else "{}")[:4000],
             (briefing.model_dump_json() if briefing else "{}")[:4000],
             model, int(bool(ok)), (error or "")[:500], (trace_id or "")[:64]))
        conn.commit()
    except Exception as e:
        log.warning("council report save failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass


def _note_headlines(rctx: dict, snippets: list[dict], mode: str) -> None:
    """Record which headlines the news agent read (audit trail). Fail-open."""
    obs = (rctx or {}).get("observation")
    if obs is None:
        return
    try:
        obs.update(output={"mode": mode, "headlines": [
            {"id": s.get("id"), "title": s.get("title")} for s in snippets]})
    except Exception as e:
        log.warning("retrieve span update failed: %s", e)


def run_council(asset: str, cfg: dict, conn) -> dict | None:
    """Synchronous council. Returns briefing dict or None. Never raises."""
    from src.ai_agents import agents
    from src.ai_agents.context import facts_text, portfolio_facts, setup_facts
    from src.ai_agents.llm import enabled
    from src.ai_agents.rag.retrieve import retrieve
    from src.ai_agents.tracing import flush as tracing_flush
    from src.ai_agents.tracing import init as tracing_init
    from src.ai_agents.tracing import span as trace_span

    if not enabled(cfg):
        return None
    tracing_init(cfg)
    model = cfg.get("ai", {}).get("model", "")
    setup = setup_facts(conn, asset)
    pf = portfolio_facts(conn, asset, cfg)
    state = str(setup.get("state"))
    try:
        with trace_span("run_council", tags=["council", asset],
                        metadata={"asset": asset, "state": state}) as tctx:
            tid = tctx.get("trace_id") or ""
            root_obs = tctx.get("observation_id")
            with trace_span("rag_retrieve", trace_id=tid,
                            parent_observation_id=root_obs,
                            as_type="retriever") as rctx:
                try:
                    snippets, mode = retrieve(conn, cfg, asset)
                except Exception as e:
                    log.warning("council retrieve failed: %s", e)
                    snippets, mode = [], "sql"
                _note_headlines(rctx, snippets, mode)
            setup["news_mode"] = mode

            def _news_job():
                with trace_span("run_news", trace_id=tid,
                                parent_observation_id=root_obs) as nctx:
                    return agents.run_news(conn, cfg, snippets, _trace=nctx)

            def _risk_job(facts: str):
                with trace_span("run_risk", trace_id=tid,
                                parent_observation_id=root_obs) as rictx:
                    return agents.run_risk(conn, cfg, facts, _trace=rictx)

            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                    fn = ex.submit(_news_job)
                    fr = ex.submit(_risk_job, facts_text(setup, pf))
                    news = fn.result()
                    risk = fr.result()
                with trace_span("run_chief", trace_id=tid,
                                parent_observation_id=root_obs) as cctx:
                    briefing = agents.run_chief(conn, cfg, news, risk, asset, state,
                                                _trace=cctx)
                _save_report(conn, asset, setup, news, risk, briefing, model, True,
                             trace_id=tid)
                return {"asset": asset, "news": news.model_dump(),
                        "risk": risk.model_dump(), "briefing": briefing.model_dump(),
                        "setup": setup, "trace_id": tid or None}
            except Exception as e:
                log.warning("council failed for %s: %s", asset, e)
                _save_report(conn, asset, setup, None, None, None, model, False,
                             str(e), trace_id=tid)
                return None
    finally:
        tracing_flush()


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
