"""Pydantic schemas for strict agent outputs. Schema version is stored per report."""

from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = 1


class NewsView(BaseModel):
    model_config = {"extra": "forbid"}
    sentiment: Literal["bullish", "bearish", "neutral"] = "neutral"
    catalysts: list[str] = Field(default_factory=list, max_length=5)
    risks: list[str] = Field(default_factory=list, max_length=5)
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)
    confidence: Literal["low", "medium", "high"] = "low"

    def validated(self, known_ids: set[str]) -> "NewsView":
        ev = [i for i in self.evidence_ids if i in known_ids]
        if not ev:
            return NewsView(sentiment="neutral", catalysts=[], risks=[],
                            evidence_ids=[], confidence="low")
        return NewsView(sentiment=self.sentiment, catalysts=self.catalysts[:5],
                        risks=self.risks[:5], evidence_ids=ev[:12],
                        confidence=self.confidence)


class RiskView(BaseModel):
    model_config = {"extra": "forbid"}
    concentration: Literal["high", "medium", "low"] = "low"
    notes: list[str] = Field(default_factory=list, max_length=5)


class Briefing(BaseModel):
    model_config = {"extra": "forbid"}
    tone: Literal["supportive", "neutral", "caution"] = "neutral"
    bullets: list[str] = Field(default_factory=list, max_length=6)


class AssetDiagnosis(BaseModel):
    model_config = {"extra": "forbid"}
    state_summary: str = Field(default="", max_length=500)
    blockers: list[str] = Field(default_factory=list, max_length=5)
    watchers: list[str] = Field(default_factory=list, max_length=5)
