from app.domain.models import NewsEvent
from app.services.entity_resolution import EntityResolutionService
from app.services.source_reliability import SourceReliabilityService


def test_resolves_common_nse_aliases() -> None:
    service = EntityResolutionService.default()
    assert service.symbols_for("TCS wins a major digital transformation deal") == ["TCS"]
    assert service.symbols_for("Reliance Industries announces new investment") == ["RELIANCE"]
    assert service.symbols_for("SBI and HDFC Bank see strong demand") == ["SBIN", "HDFCBANK"]


def test_does_not_match_partial_words() -> None:
    service = EntityResolutionService.default()
    assert service.symbols_for("RelianceX reports results") == []


def test_enrich_merges_existing_and_resolved_symbols() -> None:
    service = EntityResolutionService.default()
    event = NewsEvent(
        id="1",
        title="Infosys and TCS announce partnership",
        source="test",
        published_at="2026-09-07T00:00:00+00:00",
        symbols=["CUSTOM"],
    )
    enriched = service.enrich(event)
    assert enriched.symbols == ["CUSTOM", "INFY", "TCS"]


def test_source_reliability_uses_tiers() -> None:
    service = SourceReliabilityService.default()
    assert service.score("Reuters").score == 0.95
    assert service.score("Reuters").tier == "A"
    assert service.score("unknown source").score == 0.50
    assert service.score("unknown source").tier == "C"
