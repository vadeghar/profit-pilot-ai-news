import json
import re

from app.domain.models import AiDecision, NewsEvent
from app.storage import MarketKnowledgeRepository


class MarketKnowledgeService:
    """Build a small relevant context window from previously analyzed news."""

    def __init__(self, repository: MarketKnowledgeRepository, *, max_items: int = 6) -> None:
        if max_items <= 0:
            raise ValueError("max_items must be greater than zero")
        self.repository = repository
        self.max_items = max_items

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {
            token.lower()
            for token in re.findall(r"[A-Za-z0-9]{4,}", text)
            if token.lower() not in {"that", "this", "with", "from", "into", "will", "after", "before"}
        }

    def relevant_context(self, event: NewsEvent) -> list[str]:
        event_tokens = self._tokens(event.title)
        event_symbols = {symbol.upper() for symbol in event.symbols}
        scored: list[tuple[float, str]] = []

        for row in self.repository.list_recent(limit=200):
            try:
                symbols = {str(value).upper() for value in json.loads(row["symbols_json"])}
                keywords = {str(value).lower() for value in json.loads(row["keywords_json"])}
            except (TypeError, json.JSONDecodeError):
                continue

            symbol_overlap = len(event_symbols & symbols)
            keyword_overlap = len(event_tokens & keywords)
            if symbol_overlap == 0 and keyword_overlap == 0:
                continue

            score = symbol_overlap * 10 + keyword_overlap * 2 + float(row["confidence"])
            scored.append(
                (
                    score,
                    f"- Symbols: {', '.join(sorted(symbols)) or 'NONE'}; "
                    f"Signal: {row['signal']}; Confidence: {float(row['confidence']):.2f}; "
                    f"Prior context: {row['knowledge_text']}",
                )
            )

        scored.sort(key=lambda item: item[0], reverse=True)
        return [context for _, context in scored[: self.max_items]]

    def record(self, event: NewsEvent, decision: AiDecision) -> None:
        keywords = sorted(self._tokens(event.title) | {symbol.lower() for symbol in event.symbols})
        self.repository.save(event, decision, keywords)
