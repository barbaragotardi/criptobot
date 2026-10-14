"""News ingest: RSS -> parse -> classify -> persist -> embed new only."""

import logging
import time

log = logging.getLogger(__name__)

BATCH = 50


def ingest_once(conn, cfg: dict) -> dict:
    """Fetch feeds, insert new rows, embed NULLs in batches. Never raises."""
    from src.ai_agents.rag.embed import doc_text, embed_texts, vec_literal, log_embed_call
    from src.market.news import fetch_news

    stats = {"fetched": 0, "new": 0, "embedded": 0}
    try:
        articles = fetch_news(cfg=cfg)
    except Exception as e:
        log.warning("news ingest fetch failed: %s", e)
        return stats
    stats["fetched"] = len(articles)
    a = cfg.get("ai", {})
    emb_model = a.get("embedding_model", "gemini-embedding-2")
    emb_dim = int(a.get("embedding_dim", 768))
    for art in articles:
        try:
            pub = art.published_at.isoformat() if art.published_at else None
            conn.execute(
                "INSERT INTO news_articles (id, source, title, summary, url,"
                " published_at, category, tags, fetched_ts, embedding_model, embedding_dim)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING",
                (art.id, art.source_name, art.title, art.summary, art.url, pub,
                 art.category, list(art.tags or []), int(time.time() * 1000),
                 emb_model, emb_dim),
            )
        except Exception as e:
            log.warning("news insert failed: %s", e)
    try:
        conn.commit()
    except Exception:
        conn.rollback()
    row = conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()
    _ = row
    # Backfill NULL embeddings.
    try:
        pending = conn.execute(
            "SELECT id, title, summary FROM news_articles WHERE embedding IS NULL"
            " ORDER BY fetched_ts DESC LIMIT 200").fetchall()
    except Exception as e:
        log.warning("news pending query failed (no vector col?): %s", e)
        return stats
    stats["new"] = len(pending)
    for i in range(0, len(pending), BATCH):
        chunk = pending[i:i + BATCH]
        texts = [doc_text(t or "", s or "") for _, t, s in chunk]
        t0 = time.time()
        vecs = embed_texts(texts, cfg)
        ms = int((time.time() - t0) * 1000)
        ok = any(v is not None for v in vecs)
        log_embed_call(conn, len(chunk), ms, ok, "" if ok else "batch failed")
        for (aid, _, _), v in zip(chunk, vecs):
            if v is None:
                continue
            try:
                conn.execute(
                    "UPDATE news_articles SET embedding=%s::vector WHERE id=%s",
                    (vec_literal(v), aid))
                stats["embedded"] += 1
            except Exception as e:
                log.warning("embed update failed: %s", e)
    try:
        conn.commit()
    except Exception:
        conn.rollback()
    # Retention prune.
    try:
        days = int(a.get("rag", {}).get("retention_days", 365))
        conn.execute(
            "DELETE FROM news_articles WHERE fetched_ts < %s",
            (int(time.time() * 1000) - days * 86400 * 1000,))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    return stats
