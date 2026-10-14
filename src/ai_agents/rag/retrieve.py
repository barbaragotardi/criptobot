"""Retrieve news snippets for an asset: vector ranking + SQL fallback."""

import logging
import time

log = logging.getLogger(__name__)


def _aliases(cfg: dict, asset: str) -> list[str]:
    m = (cfg.get("ai", {}).get("asset_aliases", {}) or {})
    return [str(x) for x in m.get(asset, [asset])]


def _snippet(row) -> dict:
    return {"id": str(row[0]), "source": row[1] or "", "title": row[2] or "",
            "summary": (row[3] or "")[:400], "url": row[4] or "",
            "published_at": str(row[5] or ""), "score": float(row[6] or 0)}


def retrieve(conn, cfg: dict, asset: str, max_age_hours: int | None = None,
             top_k: int | None = None) -> tuple[list[dict], str]:
    """Returns (snippets, mode) where mode is 'vector' or 'sql'."""
    from src.ai_agents.rag.embed import embed_query, vec_literal

    rag = cfg.get("ai", {}).get("rag", {})
    hours = max_age_hours if max_age_hours is not None else int(rag.get("news_max_age_hours", 48))
    k = top_k if top_k is not None else int(rag.get("max_headlines", 12))
    min_sim = float(rag.get("min_similarity", 0.30))
    cutoff_ms = int(time.time() * 1000) - hours * 3600 * 1000
    aliases = _aliases(cfg, asset)
    like = "%" + "%".join([]) + "%"
    _ = like

    qvec = embed_query(f"{asset} {' '.join(aliases)} crypto news", cfg)
    if qvec is not None:
        try:
            rows = conn.execute(
                "SELECT id, source, title, summary, url, published_at,"
                " 1 - (embedding <=> %s::vector) AS sim"
                " FROM news_articles WHERE fetched_ts >= %s AND embedding IS NOT NULL"
                " ORDER BY embedding <=> %s::vector LIMIT %s",
                (vec_literal(qvec), cutoff_ms, vec_literal(qvec), k * 3),
            ).fetchall()
            # Asset filter: keep rows mentioning an alias, plus top macro hits.
            als = [x.lower() for x in aliases]
            kept, macro = [], []
            for r in rows:
                if float(r[6] or 0) < min_sim:
                    continue
                txt = f"{r[2] or ''} {r[3] or ''}".lower()
                if any(x.lower() in txt for x in als):
                    kept.append(r)
                elif len(macro) < 3:
                    macro.append(r)
            picked = (kept + macro)[:k]
            if picked:
                return [_snippet(r) for r in _dedup(picked, cfg)], "vector"
        except Exception as e:
            log.warning("vector retrieve failed, sql fallback: %s", e)
            try:
                conn.rollback()
            except Exception:
                pass
    # SQL fallback: alias ILIKE + recency.
    try:
        conds = " OR ".join(["title ILIKE %s OR summary ILIKE %s"] * len(aliases))
        params: list = []
        for x in aliases:
            params += [f"%{x}%", f"%{x}%"]
        rows = conn.execute(
            f"SELECT id, source, title, summary, url, published_at, 0.0"
            f" FROM news_articles WHERE fetched_ts >= %s AND ({conds})"
            f" ORDER BY fetched_ts DESC LIMIT %s",
            (cutoff_ms, *params, k),
        ).fetchall()
        return [_snippet(r) for r in rows], "sql"
    except Exception as e:
        log.warning("sql retrieve failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return [], "sql"


def _dedup(rows, cfg: dict) -> list:
    """Near-duplicate collapse by title token overlap (>=0.8). Keeps highest score."""
    thr = 0.8
    _ = cfg
    out = []
    seen: list[set] = []
    for r in sorted(rows, key=lambda x: float(x[6] or 0), reverse=True):
        toks = set((r[2] or "").lower().split())
        if not toks:
            out.append(r)
            continue
        dup = False
        for s in seen:
            inter = len(toks & s)
            union = len(toks | s) or 1
            if inter / union >= thr:
                dup = True
                break
        if not dup:
            seen.append(toks)
            out.append(r)
    return out
