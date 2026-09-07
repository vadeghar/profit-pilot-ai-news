from app.services.source_reliability import SourceReliabilityRegistry


def test_known_source_gets_configured_score_and_tier() -> None:
    registry = SourceReliabilityRegistry()
    result = registry.evaluate("Reuters")
    assert result.score == 0.95
    assert result.tier == "A"


def test_unknown_source_gets_conservative_neutral_default() -> None:
    registry = SourceReliabilityRegistry()
    result = registry.evaluate("Unknown Feed")
    assert result.score == 0.50
    assert result.tier == "D"


def test_overrides_are_clamped() -> None:
    registry = SourceReliabilityRegistry({"Custom": 2.0, "Low": -1.0})
    assert registry.score("Custom") == 1.0
    assert registry.score("Low") == 0.0
