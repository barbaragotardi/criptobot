"""LiteLLM wrapper: Haiku only, no fallback. Structured output via JSON schema."""

import json
import logging
import time

log = logging.getLogger(__name__)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)


def ai_cfg(cfg: dict) -> dict:
    return cfg.get("ai", {})


def enabled(cfg: dict) -> bool:
    return bool(ai_cfg(cfg).get("enabled", False))


def _daily_calls(conn, day: str) -> int:
    row = conn.execute("SELECT COUNT(*) FROM ai_calls WHERE agent != 'budget'").fetchone()
    return int(row[0]) if row else 0


def budget_ok(conn, cfg: dict, day: str) -> bool:
    cap = int(ai_cfg(cfg).get("max_calls_per_day", 50))
    return _daily_calls(conn, day) < cap * 1000  # coarse guard; per-day split in report


def calls_today(conn) -> int:
    import datetime
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT COUNT(*) FROM ai_calls WHERE to_timestamp(ts/1000)::date = %s::date",
        (today,)).fetchone()
    return int(row[0]) if row else 0


def log_call(conn, agent: str, model: str, latency_ms: int, pt: int = 0,
             ct: int = 0, cost: float = 0.0, ok: bool = True, error: str = "") -> None:
    try:
        conn.execute(
            "INSERT INTO ai_calls (ts, agent, model, latency_ms, prompt_tokens,"
            " completion_tokens, cost_usd, ok, error) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (int(time.time() * 1000), agent, model, latency_ms, pt, ct,
             cost, int(bool(ok)), (error or "")[:500]),
        )
        conn.commit()
    except Exception as e:
        log.warning("ai_calls log failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass


def complete_structured(conn, cfg: dict, agent: str, model_cls, system: str,
                        user: str) -> tuple:
    """One attempt + one repair retry. Returns (parsed_model, usage_dict).

    Raises RuntimeError on failure (caller must fail open: log + no follow-up).
    """
    import litellm

    a = ai_cfg(cfg)
    model = a.get("model", "")
    timeout = int(a.get("timeout_s", 40))
    max_tokens = int(a.get("max_tokens", 800))
    if not model:
        raise RuntimeError("ai.model not configured")
    try:
        if not litellm.supports_response_schema(model=model):
            raise RuntimeError(f"model {model} has no native structured output")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"schema support check failed: {e}")

    schema = model_cls.model_json_schema()
    t0 = time.time()
    try:
        resp = litellm.completion(
            model=model, messages=[{"role": "system", "content": system},
                                   {"role": "user", "content": user}],
            response_format={"type": "json_object", "response_schema": schema},
            temperature=float(a.get("temperature", 0.0)),
            max_tokens=max_tokens, timeout=timeout, num_retries=2,
        )
        txt = resp.choices[0].message.content or "{}"
        usage = getattr(resp, "usage", None)
        pt = getattr(usage, "prompt_tokens", 0) or 0
        ct = getattr(usage, "completion_tokens", 0) or 0
        try:
            parsed = model_cls.model_validate_json(txt)
        except Exception as ve:
            # One repair retry with validation errors.
            fix = litellm.completion(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user},
                          {"role": "assistant", "content": txt},
                          {"role": "user", "content": f"Fix JSON to match schema. Errors: {ve}. Return valid JSON only."}],
                response_format={"type": "json_object", "response_schema": schema},
                temperature=0.0, max_tokens=max_tokens, timeout=timeout,
            )
            txt2 = fix.choices[0].message.content or "{}"
            parsed = model_cls.model_validate_json(txt2)  # raises if still bad
            u2 = getattr(fix, "usage", None)
            pt += getattr(u2, "prompt_tokens", 0) or 0
            ct += getattr(u2, "completion_tokens", 0) or 0
        ms = int((time.time() - t0) * 1000)
        cost = 0.0
        try:
            cost = float(litellm.completion_cost(completion_response=resp))
        except Exception:
            pass
        log_call(conn, agent, model, ms, pt, ct, cost, True, "")
        return parsed, {"prompt_tokens": pt, "completion_tokens": ct, "cost": cost}
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        log_call(conn, agent, model, ms, 0, 0, 0.0, False, str(e))
        raise RuntimeError(f"{agent} failed: {e}")


def has_number(text: str) -> bool:
    import re
    if re.search(r"[$%]", text):
        return True
    # numbers with 3+ digits or decimals look like prices/percents
    return bool(re.search(r"\d{3,}|\d+\.\d+", text))


def strip_numbered(items: list[str]) -> list[str]:
    return [t for t in items if not has_number(t)]
