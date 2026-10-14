"""Pydantic schemas for strict agent outputs. Schema version is stored per report."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

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


class NewsView(BaseModel):
    model_config = {"extra": "forbid"}
    sentiment: Literal["bullish", "bearish", "neutral"] = "neutral"
    catalysts: list[NewsTopic] = Field(default_factory=list, max_length=5)
    risks: list[NewsTopic] = Field(default_factory=list, max_length=5)
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)
    confidence: Literal["low", "medium", "high"] = "low"
    rationale: str = Field(default="", max_length=140)

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


class AssetDiagnosis(BaseModel):
    model_config = {"extra": "forbid"}
    blockers: list[Blocker] = Field(default_factory=list, max_length=5)
    watchers: list[Watcher] = Field(default_factory=list, max_length=5)
