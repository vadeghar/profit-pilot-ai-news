from pathlib import Path

import pytest

from app.domain.models import AiDecision, NewsEvent, PaperOrder, Position, Signal
from app.providers.stub_market_data import StubMarketDataProvider
from app.services.market_brain import MarketBrainService
from app.services.portfolio import PortfolioService
from app.storage import AiDecisionRepository, NewsEventRepository, PaperTradingRepository, SqliteDatabase


@pytest.mark.asyncio
async def test_market_brain_builds_news_ai_trade_and_position_graph(tmp_path: Path) -> None:
    database = SqliteDatabase(f"sqlite:///{tmp_path / 'brain.db'}")
    database.initialize()
    news_repository = NewsEventRepository(database)
    decision_repository = AiDecisionRepository(database)
    paper_repository = PaperTradingRepository(database)

    event = NewsEvent(
        id="event-1",
        title="Reliance earnings beat expectations",
        source="test",
        published_at="2026-09-07T09:00:00+00:00",
        symbols=["RELIANCE"],
        materiality=0.9,
    )
    news_repository.save(event)
    decision_repository.save(
        event.id,
        AiDecision(
            signal=Signal.BUY,
            confidence=0.88,
            reasoning="Positive earnings surprise should support the stock.",
            prompt_version="news-impact-v1",
            model="test-model",
        ),
        prompt="test prompt",
        input_snapshot="{}",
    )
    paper_repository.save_execution(
        PaperOrder(
            id="order-1",
            event_id=event.id,
            symbol="RELIANCE",
            side=Signal.BUY,
            quantity=10,
            fill_price=1_500.0,
            notional=15_000.0,
            status="FILLED",
            created_at="2026-09-07T09:01:00+00:00",
        ),
        Position(symbol="RELIANCE", quantity=10, average_price=1_500.0, realized_pnl=0),
    )

    service = MarketBrainService(
        news_repository,
        decision_repository,
        paper_repository,
        PortfolioService(paper_repository, StubMarketDataProvider()),
    )
    snapshot = await service.snapshot()

    node_ids = {node.id for node in snapshot.nodes}
    relations = {(edge.source, edge.target, edge.relation) for edge in snapshot.edges}

    assert "news:event-1" in node_ids
    assert "ai:event-1" in node_ids
    assert "stock:RELIANCE" in node_ids
    assert "trade:order-1" in node_ids
    assert "position:RELIANCE" in node_ids
    assert ("news:event-1", "ai:event-1", "ANALYZED") in relations
    assert ("ai:event-1", "stock:RELIANCE", "IMPACTS") in relations
    assert ("stock:RELIANCE", "trade:order-1", "EXECUTED") in relations
    assert ("trade:order-1", "position:RELIANCE", "UPDATES") in relations
