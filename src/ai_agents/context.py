"""Deterministic context builders (no LLM). Numbers are computed here, never by the model."""

import time


def setup_facts(conn, asset: str) -> dict:
    row = conn.execute(
        "SELECT state, ema, entry, stop, tp, rr FROM asset_state WHERE asset=%s",
        (asset,)).fetchone()
    if not row:
        return {"asset": asset, "state": "UNKNOWN"}
    return {"asset": asset, "state": row[0], "ema": row[1], "entry": row[2],
            "stop": row[3], "tp": row[4], "rr": row[5]}


def portfolio_facts(conn, asset: str, cfg: dict) -> dict:
    try:
        open_n = conn.execute(
            "SELECT COUNT(*) FROM paper_positions WHERE status='OPEN'").fetchone()[0]
    except Exception:
        open_n = 0
    try:
        corr = conn.execute(
            "SELECT COUNT(*) FROM paper_positions WHERE status='OPEN' AND asset != 'BTC'").fetchone()[0]
    except Exception:
        corr = 0
    exp = cfg.get("exposure", {})
    facts: dict = {"open_positions": int(open_n or 0),
                   "correlated_open": int(corr or 0),
                   "max_open": exp.get("max_open_signals"),
                   "max_correlated": exp.get("max_correlated_exposure"),
                   "asset_has_paper_open": False,
                   "portfolio_qty": 0.0, "portfolio_avg": 0.0}
    try:
        r = conn.execute(
            "SELECT 1 FROM paper_positions WHERE status='OPEN' AND asset=%s LIMIT 1",
            (asset,)).fetchone()
        facts["asset_has_paper_open"] = bool(r)
    except Exception:
        pass
    try:
        rows = conn.execute(
            "SELECT quantity, price, remaining_qty FROM portfolio_trades"
            " WHERE asset=%s AND side='BUY'", (asset,)).fetchall()
        qty = sum(float(x[2] if x[2] is not None else 0) for x in rows)
        cost = sum(float(x[2] if x[2] is not None else 0) * float(x[1] or 0) for x in rows)
        facts["portfolio_qty"] = qty
        facts["portfolio_avg"] = (cost / qty) if qty > 0 else 0.0
    except Exception:
        pass
    return facts


def facts_text(setup: dict, pf: dict) -> str:
    has_manual = "sim" if (pf.get("portfolio_qty") or 0) > 0 else "nao"
    return (
        f"Ativo {setup.get('asset')} estado {setup.get('state')}."
        f" Posicoes paper abertas: {pf['open_positions']} (correlacionadas {pf['correlated_open']})."
        f" Este ativo com paper aberto: {pf['asset_has_paper_open']}."
        f" Carteira manual no ativo: {has_manual}."
        " Comente apenas estes fatos, sem inventar numeros."
    )


def budget_key() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def command_allowed(conn, cfg: dict, chat: str, cmd: str) -> tuple[bool, str]:
    """Per-chat cooldown stored in memory table ai_calls (last ts per agent)."""
    cool = int(cfg.get("ai", {}).get("command_cooldown_s", 60))
    try:
        row = conn.execute(
            "SELECT MAX(ts) FROM ai_calls WHERE agent=%s", (f"cmd:{chat}:{cmd}",)).fetchone()
        last = int(row[0] or 0)
        now_ms = int(time.time() * 1000)
        if now_ms - last < cool * 1000:
            return False, f"Aguarde {cool}s entre consultas."
        conn.execute(
            "INSERT INTO ai_calls (ts, agent, model) VALUES (%s,%s,'')",
            (now_ms, f"cmd:{chat}:{cmd}"))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    cap = int(cfg.get("ai", {}).get("max_calls_per_day", 50))
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM ai_calls WHERE agent NOT LIKE 'cmd:%'"
            " AND ts >= %s", (int(time.time() * 1000) - 86400 * 1000,)).fetchone()[0]
        if int(n or 0) >= cap:
            return False, "Limite diário de consultas IA atingido."
    except Exception:
        pass
    return True, "ok"
