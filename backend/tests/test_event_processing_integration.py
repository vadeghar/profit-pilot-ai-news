from pathlib import Path

import pytest

from app.domain.models import AiDecision, MarketPhase, NewsEvent, Signal
from app.providers.interfaces import LlmProvider, MarketDataProvider
from app.services.ai_analysis import AiAnalysisService
from app.services.event_processing import EventProcessingService
from app.services.paper_trading import PaperTradingService
from app.services.risk_engine import RiskConfig, RiskEngine
from app.storage import AiDecisionRepository, NewsEventRepository, PaperTradingRepository, SqliteDatabase


class FakeLlm(LlmProvider):
    async def analyze(self, event: NewsEvent, prompt: str) -> AiDecision:
        return AiDecision(
            signal=Signal.BUY,
            confidence=0.90,
            reasoning="Material positive test event.",
            prompt_version="news-impact-v2",
            model="test-llm",
        )


class FakeMarketData(MarketDataProvider):
    async def last_price(self, symbol: str) -> float:
        return 100.0


@pytest.mark.asyncio
async def test_event_processing_executes_once_and_persists_state(tmp_path: Path) -> None:
    database = SqliteDatabase(f"sqlite:///{tmp_path / 'profit_pilot.db'}")
    database.initialize()
    news_repository = NewsEventRepository(database)
    decision_repository = AiDecisionRepository(database)
    paper_repository = PaperTradingRepository(database)

    event = NewsEvent(
        id="integration-1",
        title="Reliance Industries reports strong growth",
        source="Reuters",
        published_at="2026-09-07T10:00:00+05:30",
        symbols=["RELIANCE"],
        materiality=0.90,
    )
    news_repository.save(event)

    ai = AiAnalysisService(news_repository, decision_repository, FakeLlm())
    risk = RiskEngine(FakeMarketData(), RiskConfig(max_order_notional=10_000, max_order_quantity=10))
    paper = PaperTradingService(paper_repository)
    processing = EventProcessingService(news_repository, ai, risk, paper, paper_repository)

    result = await processing.process(event.id, quantity=2, market_phase=MarketPhase.MARKET_HOURS)

    assert result.status == "EXECUTED"
    assert result.execution is not None
    assert result.execution.order.symbol == "RELIANCE"
    assert result.execution.order.quantity == 2
    assert result.execution.order.fill_price == 100.0
    assert paper_repository.has_order_for_event(event.id)
    assert paper_repository.get_position("RELIANCE").quantity == 2

    repeated = await processing.process(event.id, quantity=2, market_phase=MarketPhase.MARKET_HOURS)
    assert repeated.status == "ALREADY_EXECUTED"
    assert len(paper_repository.list_orders()) == 1
    assert len(decision_repository.list_for_event(event.id)) == 1
