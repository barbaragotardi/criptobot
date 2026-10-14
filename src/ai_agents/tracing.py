"""Langfuse tracing for the AI layer. Fail-open: never raises, never blocks the bot.

Design: LiteLLM `langfuse` callbacks log every Haiku call (tokens + cost).
Spans are created explicitly with trace_id/parent IDs passed in `metadata`,
so the tree (run_council -> run_news || run_risk -> run_chief) holds even
across the ThreadPoolExecutor threads (contextvars do not propagate there).
"""

import contextlib
import logging
import os

log = logging.getLogger(__name__)

_CLIENT = None
_ENABLED = False
_INIT_DONE = False


def _obs_cfg(cfg: dict) -> dict:
    return (cfg.get("ai", {}).get("observability", {}).get("langfuse", {}) or {})


def is_enabled() -> bool:
    return _ENABLED and _CLIENT is not None


def init(cfg: dict) -> bool:
    """Idempotent. Registers LiteLLM callbacks. Returns True when tracing is on."""
    global _CLIENT, _ENABLED, _INIT_DONE
    if _INIT_DONE:
        return is_enabled()
    _INIT_DONE = True
    try:
        if not _obs_cfg(cfg).get("enabled", False):
            return False
        if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
            log.warning("langfuse enabled but keys missing; tracing off")
            return False
        import litellm
        from langfuse import Langfuse

        _CLIENT = Langfuse()  # reads LANGFUSE_* from env
        for cb in ("success_callback", "failure_callback"):
            cur = getattr(litellm, cb)
            if "langfuse" not in cur:
                cur.append("langfuse")
        _ENABLED = True
        log.info("langfuse tracing on")
    except Exception as e:
        log.warning("langfuse init failed, tracing off: %s", e)
        _CLIENT, _ENABLED = None, False
    return is_enabled()


def new_trace_id() -> str:
    try:
        if _CLIENT is not None:
            return _CLIENT.create_trace_id()
    except Exception:
        pass
    import secrets
    return secrets.token_hex(16)


@contextlib.contextmanager
def span(name: str, trace_id: str | None = None,
         parent_observation_id: str | None = None,
         as_type: str = "span", tags: list[str] | None = None,
         metadata: dict | None = None):
    """Yield {"trace_id", "observation_id", "observation"}. No-op dict when off."""
    if not is_enabled():
        yield {"trace_id": trace_id or "", "observation_id": parent_observation_id,
               "observation": None}
        return
    try:
        from langfuse.types import TraceContext

        tid = trace_id or new_trace_id()
        md = dict(metadata or {})
        if tags:
            md.setdefault("tags", list(tags))
        ctx = (TraceContext(trace_id=tid, parent_span_id=parent_observation_id)
               if parent_observation_id else TraceContext(trace_id=tid))
        with _CLIENT.start_as_current_observation(
                name=name, as_type=as_type, trace_context=ctx,
                metadata=md) as obs:
            yield {"trace_id": _CLIENT.get_current_trace_id() or tid,
                   "observation_id": _CLIENT.get_current_observation_id(),
                   "observation": obs}
    except Exception as e:
        log.warning("langfuse span %s failed: %s", name, e)
        yield {"trace_id": trace_id or "", "observation_id": parent_observation_id,
               "observation": None}


def llm_metadata(agent: str, trace: dict | None = None,
                 tags: list[str] | None = None) -> dict:
    """Metadata for litellm.completion. Links the generation into the span tree."""
    if not is_enabled():
        return {}
    md: dict = {"generation_name": agent}
    if trace:
        if trace.get("trace_id"):
            md["trace_id"] = trace["trace_id"]
        if trace.get("observation_id"):
            md["parent_observation_id"] = trace["observation_id"]
    if tags:
        md["tags"] = tags
    return md


def flush() -> None:
    if not is_enabled():
        return
    try:
        _CLIENT.flush()
    except Exception as e:
        log.warning("langfuse flush failed: %s", e)
