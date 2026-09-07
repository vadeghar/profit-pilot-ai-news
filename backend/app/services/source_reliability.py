from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceReliability:
    source: str
    score: float
    tier: str


class SourceReliabilityService:
    """Deterministic source-quality scoring, kept separate from AI materiality."""

    def __init__(self, scores: dict[str, float] | None = None, default_score: float = 0.50) -> None:
        self.scores = {key.casefold(): max(0.0, min(1.0, value)) for key, value in (scores or {}).items()}
        self.default_score = max(0.0, min(1.0, default_score))

    @classmethod
    def default(cls) -> "SourceReliabilityService":
        return cls({
            "reuters": 0.95,
            "reuters india": 0.95,
            "the economic times": 0.90,
            "economic times": 0.90,
            "business standard": 0.90,
            "moneycontrol": 0.85,
            "livemint": 0.85,
            "mint": 0.85,
            "nse": 0.98,
            "bse": 0.98,
            "sebi": 1.00,
            "company filing": 1.00,
            "google news": 0.55,
        })

    def score(self, source: str) -> SourceReliability:
        normalized = source.casefold().strip()
        score = self.scores.get(normalized, self.default_score)
        if score >= 0.90:
            tier = "A"
        elif score >= 0.75:
            tier = "B"
        elif score >= 0.50:
            tier = "C"
        else:
            tier = "D"
        return SourceReliability(source=source, score=score, tier=tier)
