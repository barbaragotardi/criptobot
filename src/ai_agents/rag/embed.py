"""Gemini embeddings via native google-genai SDK (model gemini-embedding-2)."""

import logging
import time

log = logging.getLogger(__name__)


def embed_texts(texts: list[str], cfg: dict) -> list[list[float] | None]:
    """Return one vector per input (None on failure per item). Batch in one call."""
    from google import genai
    from google.genai import types

    a = cfg.get("ai", {})
    model = a.get("embedding_model", "gemini-embedding-2")
    dim = int(a.get("embedding_dim", 768))
    if not texts:
        return []
    client = genai.Client()  # reads GEMINI_API_KEY from env
    out: list[list[float] | None] = [None] * len(texts)
    try:
        res = client.models.embed_content(
            model=model,
            contents=texts,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_DOCUMENT",
                output_dimensionality=dim,
            ),
        )
        for i, e in enumerate(res.embeddings or []):
            vals = list(e.values or [])
            if len(vals) == dim:
                out[i] = vals
            else:
                log.warning("embed dim mismatch: got %d want %d", len(vals), dim)
        return out
    except Exception as e:
        log.warning("gemini embed batch failed (%d texts): %s", len(texts), e)
        return out


def embed_query(text: str, cfg: dict) -> list[float] | None:
    from google import genai
    from google.genai import types

    a = cfg.get("ai", {})
    model = a.get("embedding_model", "gemini-embedding-2")
    dim = int(a.get("embedding_dim", 768))
    try:
        client = genai.Client()
        res = client.models.embed_content(
            model=model, contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY", output_dimensionality=dim),
        )
        vals = list((res.embeddings or [None])[0].values or [])
        return vals if len(vals) == dim else None
    except Exception as e:
        log.warning("gemini embed query failed: %s", e)
        return None


def doc_text(title: str, summary: str) -> str:
    return f"{title or ''} {(summary or '')[:500]}".strip()


def vec_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def log_embed_call(conn, n: int, ms: int, ok: bool, err: str = "") -> None:
    from src.ai_agents.llm import log_call
    log_call(conn, "embedding", "gemini-embedding-2", ms, 0, 0, 0.0, ok, err)
    _ = n
    _ = time.time()
