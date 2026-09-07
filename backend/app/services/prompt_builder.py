from app.domain.models import NewsEvent
from app.services.entity_resolution import CompanyEntityResolver
from app.services.source_reliability import SourceReliabilityRegistry

PROMPT_VERSION = "news-impact-v2"


def build_news_impact_prompt(
    event: NewsEvent,
    *,
    resolver: CompanyEntityResolver | None = None,
    source_reliability: SourceReliabilityRegistry | None = None,
) -> str:
    reliability = source_reliability.evaluate(event.source) if source_reliability else None
    entities = resolver.resolve(event.title) if resolver else []

    symbols = ", ".join(event.symbols) if event.symbols else "NONE"
    if entities:
        entity_context = "\n".join(
            f"- {match.symbol}: {match.canonical_name} (matched: {match.matched_alias}; confidence: {match.confidence:.2f})"
            for match in entities
        )
    else:
        entity_context = "- NONE"

    reliability_context = (
        f"{reliability.score:.2f} (Tier {reliability.tier}; {reliability.reason})"
        if reliability
        else "NOT_AVAILABLE"
    )

    return f"""You are an Indian equity-news impact analyst.

Analyze the following news event for short-term NSE-listed equity impact.
Do not invent facts, prices, targets, or catalysts that are not present in the input.
Return a conservative structured decision with exactly one signal: BUY, SELL, or IGNORE.
The AI decision is advisory; deterministic market and risk rules are applied separately.
Source reliability and entity-resolution confidence are context signals, not trading signals by themselves.

News event:
- ID: {event.id}
- Title: {event.title}
- Source: {event.source}
- Source reliability: {reliability_context}
- Published at: {event.published_at}
- Symbols: {symbols}
- Existing materiality score: {event.materiality:.2f}

Resolved entities:
{entity_context}

Assess whether the news is likely to be materially positive, negative, or insufficiently actionable
for the named stocks. Explain the key reason and assign confidence from 0 to 1.
""".strip()
