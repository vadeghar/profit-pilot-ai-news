from app.domain.models import NewsEvent

PROMPT_VERSION = "news-impact-v1"


def build_news_impact_prompt(event: NewsEvent) -> str:
    symbols = ", ".join(event.symbols) if event.symbols else "NONE"
    return f"""You are an Indian equity-news impact analyst.

Analyze the following news event for short-term NSE-listed equity impact.
Do not invent facts, prices, targets, or catalysts that are not present in the input.
Return a conservative structured decision with exactly one signal: BUY, SELL, or IGNORE.
The AI decision is advisory; deterministic market and risk rules are applied separately.

News event:
- ID: {event.id}
- Title: {event.title}
- Source: {event.source}
- Published at: {event.published_at}
- Symbols: {symbols}
- Existing materiality score: {event.materiality:.2f}

Assess whether the news is likely to be materially positive, negative, or insufficiently actionable
for the named stocks. Explain the key reason and assign confidence from 0 to 1.
""".strip()
