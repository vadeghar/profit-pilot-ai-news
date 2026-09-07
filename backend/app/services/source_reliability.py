from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceReliability:
    source: str
    score: float
    tier: str
    reason: str


class SourceReliabilityRegistry:
    """Deterministic source-quality registry.

    Scores are metadata for ranking and AI context, not trading signals. Unknown
    sources receive a conservative neutral score until reviewed.
    """

    def __init__(self, overrides: dict[str, float] | None = None) -> None:
        self._scores = {
            "Reuters": 0.95,
            "The Economic Times": 0.85,
            "Moneycontrol": 0.80,
            "CNBC-TV18": 0.82,
            "Business Standard": 0.86,
            "Mint": 0.84,
            "The Hindu BusinessLine": 0.84,
            "Google News": 0.70,
        }
        for source, score in (overrides or {}).items():
            self._scores[source] = min(1.0, max(0.0, float(score)))

    def evaluate(self, source: str) -> SourceReliability:
        score = self._scores.get(source, 0.50)
        if score >= 0.90:
            tier = "A"
        elif score >= 0.75:
            tier = "B"
        elif score >= 0.60:
            tier = "C"
        else:
            tier = "D"
        reason = "Configured source reliability" if source in self._scores else "Unknown source; neutral default"
        return SourceReliability(source, score, tier, reason)

    def score(self, source: str) -> float:
        return self.evaluate(source).score
