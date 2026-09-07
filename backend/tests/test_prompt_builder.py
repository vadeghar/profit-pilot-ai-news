from app.domain.models import NewsEvent
from app.services.entity_catalog import resolver
from app.services.prompt_builder import PROMPT_VERSION, build_news_impact_prompt
from app.services.source_reliability import SourceReliabilityRegistry


def test_prompt_includes_entity_resolution_and_source_reliability() -> None:
    event = NewsEvent(
        id="event-1",
        title="Reliance Industries wins a major contract",
        source="Reuters",
        published_at="2026-09-07T04:00:00+00:00",
        symbols=["RELIANCE"],
        materiality=0.8,
    )

    prompt = build_news_impact_prompt(
        event,
        resolver=resolver,
        source_reliability=SourceReliabilityRegistry(),
        knowledge_context=["- Symbols: RELIANCE; Signal: BUY; Confidence: 0.80; Prior context: Positive order catalyst."],
    )

    assert PROMPT_VERSION == "news-impact-v3-market-context"
    assert "Source reliability: 0.95 (Tier A" in prompt
    assert "RELIANCE: Reliance Industries" in prompt
    assert "matched: Reliance Industries" in prompt
    assert "confidence: 1.00" in prompt
    assert "Relevant market knowledge:" in prompt
    assert "Positive order catalyst." in prompt


def test_prompt_handles_unresolved_entity_and_unknown_source() -> None:
    event = NewsEvent(
        id="event-2",
        title="A generic market update with no named company",
        source="Unknown Feed",
        published_at="2026-09-07T04:00:00+00:00",
    )

    prompt = build_news_impact_prompt(
        event,
        resolver=resolver,
        source_reliability=SourceReliabilityRegistry(),
    )

    assert "Source reliability: 0.50 (Tier D" in prompt
    assert "Resolved entities:\n- NONE" in prompt
    assert "Symbols: NONE" in prompt
    assert "Relevant market knowledge:\n- NONE" in prompt
