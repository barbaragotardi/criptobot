"""Pydantic schemas for strict agent outputs. Schema version is stored per report."""

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator

SCHEMA_VERSION = 1

NewsTopic = Literal[
    "regulation", "etf_flows", "hack_exploit", "macro_rates",
    "exchange_listing", "partnership", "protocol_upgrade", "liquidations",
    "adoption", "legal", "whale_activity", "other",
]

RiskFlag = Literal[
    "many_open_positions", "high_correlation", "already_holding_paper",
    "already_holding_manual", "near_exposure_cap",
]

Blocker = Literal[
    "market_bearish", "macro_fail", "no_pullback", "cooldown_active",
    "awaiting_confirmation", "exposure_blocked", "rr_below_min", "tp_below_min",
]

Watcher = Literal[
    "near_ema20", "near_ema50", "awaiting_confirmation", "near_support",
]

ShortText = Annotated[str, Field(max_length=140)]

# Tokens that look numeric but are technical/crypto terms, not prices.
# Placeheld before digit-stripping, restored after.
_WHITELIST_RE = re.compile(
    r"EMA\d+|\b\d+[DHdhm]\b|\bWeb3\b|\bL[12]\b|\bLayer\s?2\b"
    r"|\b(?:ERC|BRC|BEP|TRC)-?20\b|\bTop\s?\d+\b",
    re.IGNORECASE,
)
_NUM_RE = re.compile(r"\d[\d.,]*")
_MONEY_RE = re.compile(r"\s*(?:US\$|R\$|[$%])\s*")
_ORPHAN_RE = re.compile(
    r"\b(de|da|do|das|dos|em|no|na|nos|nas|ao|aos|para|pra|por|entre|at[eé]|a)\b"
    r"\s*(?=[.,;!?]|$)",
    re.IGNORECASE,
)


def sanitize_text(text: str) -> str:
    """Remove price/percent digits from LLM free text. Preserves whitelist.

    Idempotent; never raises (returns "" on bad input).
    """
    try:
        if not isinstance(text, str) or not text:
            return ""
        saved: list[str] = []

        def _hold(m: re.Match) -> str:
            saved.append(m.group(0))
            # Letter-only placeholder: digit-based ones would be eaten by _NUM_RE.
            return f"\x00{chr(ord('A') + len(saved) - 1)}\x00"

        t = _WHITELIST_RE.sub(_hold, text)
        t = _NUM_RE.sub("", t)
        t = _MONEY_RE.sub(" ", t)
        for _ in range(3):
            novo = _ORPHAN_RE.sub("", t)
            novo = re.sub(r"\s{2,}", " ", novo).strip(" ,;")
            if novo == t:
                t = novo
                break
            t = novo
        t = re.sub(r"\s{2,}", " ", t).strip(" ,;").strip()
        for i, orig in enumerate(saved):
            t = t.replace(f"\x00{chr(ord('A') + i)}\x00", orig)
        return re.sub(r"\s{2,}", " ", t).strip()
    except Exception:
        return ""


def _clean_short(value: Any) -> str:
    if not isinstance(value, str):
        return value
    return sanitize_text(value)[:140]


class NewsView(BaseModel):
    model_config = {"extra": "forbid"}
    sentiment: Literal["bullish", "bearish", "neutral"] = "neutral"
    catalysts: list[NewsTopic] = Field(default_factory=list, max_length=5)
    risks: list[NewsTopic] = Field(default_factory=list, max_length=5)
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)
    confidence: Literal["low", "medium", "high"] = "low"
    rationale: str = Field(default="", max_length=140)

    @field_validator("rationale", mode="before")
    @classmethod
    def _clean_rationale(cls, v: Any) -> Any:
        return _clean_short(v) if isinstance(v, str) else v

    def validated(self, known_ids: set[str]) -> "NewsView":
        ev = [i for i in self.evidence_ids if i in known_ids]
        if not ev:
            return NewsView(sentiment="neutral", catalysts=[], risks=[],
                            evidence_ids=[], confidence="low")
        return NewsView(sentiment=self.sentiment, catalysts=self.catalysts[:5],
                        risks=self.risks[:5], evidence_ids=ev[:12],
                        confidence=self.confidence,
                        rationale=self.rationale[:140])


class RiskView(BaseModel):
    model_config = {"extra": "forbid"}
    concentration: Literal["high", "medium", "low"] = "low"
    flags: list[RiskFlag] = Field(default_factory=list, max_length=5)


class Briefing(BaseModel):
    model_config = {"extra": "forbid"}
    tone: Literal["supportive", "neutral", "caution"] = "neutral"
    bullets: list[ShortText] = Field(default_factory=list, max_length=6)

    @field_validator("bullets", mode="before")
    @classmethod
    def _clean_bullets(cls, v: Any) -> Any:
        if not isinstance(v, list):
            return v
        return [b for b in (_clean_short(x) for x in v if isinstance(x, str)) if b][:6]


class AssetDiagnosis(BaseModel):
    model_config = {"extra": "forbid"}
    blockers: list[Blocker] = Field(default_factory=list, max_length=5)
    watchers: list[Watcher] = Field(default_factory=list, max_length=5)
