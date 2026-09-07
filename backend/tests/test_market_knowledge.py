from app.domain.models import AiDecision, NewsEvent, Signal
from app.services.market_knowledge import MarketKnowledgeService
from app.storage.ai_intelligence import MarketKnowledgeRepository
from app.storage.database import SqliteDatabase


def test_market_knowledge_retrieves_relevant_symbol_context(tmp_path) -> None:
    database = SqliteDatabase(f"sqlite:///{tmp_path / 'knowledge.db'}")
    database.initialize()
    repository = MarketKnowledgeRepository(database)
    service = MarketKnowledgeService(repository)

    previous = NewsEvent(
        id="old",
        title="Reliance telecom order strengthens outlook",
        source="test",
        published_at="2026-09-06T12:00:00Z",
        symbols=["RELIANCE"],
    )
    decision = AiDecision(
        signal=Signal.BUY,
        confidence=0.8,
        reasoning="Positive order catalyst.",
        prompt_version="test",
        model="test",
    )
    service.record(previous, decision)

    current = NewsEvent(
        id="new",
        title="Reliance announces fresh telecom investment",
        source="test",
        published_at="2026-09-07T04:00:00Z",
        symbols=["RELIANCE"],
    )

    context = service.relevant_context(current)
    assert len(context) == 1
    assert "Positive order catalyst." in context[0]
    assert "RELIANCE" in context[0]
