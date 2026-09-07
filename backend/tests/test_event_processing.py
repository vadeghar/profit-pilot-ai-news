from pathlib import Path

import pytest

from app.domain.models import AiDecision, MarketPhase, NewsEvent, Signal
from app.providers.interfaces import LlmProvider, MarketDataProvider
from app.services.ai_analysis import AiAnalysisService
from app.services.event_processing import EventProcessingService
from app.services.paper_trading import PaperTradingService
from app.services.risk_engine import RiskConfig, RiskEngine
from app.storage import AiDecisionRepository, NewsEventRepository, PaperTradingRepository, SqliteDatabase


class FixedLlmProvider(LlmProvider):
    async def analyze(self, event: NewsEvent, prompt: str) -> AiDecision:
        return AiDecision(
            signal=Signal.BUY,
            confidence=0.9,
            reasoning="Positive material event.",
            prompt_version="test-v1",
            model="test-model",
        )


class FixedMarketDataProvider(MarketDataProvider):
    async def last_price(self, symbol: str) -> float | None:
        return 100.0


def build_service(tmp_path: Path) -> tuple[EventProcessingService, NewsEventRepository, PaperTradingRepository]:
    database = SqliteDatabase(f"sqlite:///{tmp_path / 'processing.db'}")
    database.initialize()
    news_repository = NewsEventRepository(database)
    decision_repository = AiDecisionRepository(database)
    paper_repository = PaperTradingRepository(database)
    ai_analysis = AiAnalysisService(news_repository, decision_repository, FixedLlmProvider())
    risk_engine = RiskEngine(
        FixedMarketDataProvider(),
        RiskConfig(max_order_notional=10_000, max_order_quantity=100),
    )
    service = EventProcessingService(
        news_repository,
        ai_analysis,
        risk_engine,
        PaperTradingService(paper_repository),
        paper_repository,
    )
    return service, news_repository, paper_repository


@pytest.mark.asyncio
async def test_process_analyzes_applies_risk_and_executes_paper_trade(tmp_path: Path) -> None:
    service, news_repository, paper_repository = build_service(tmp_path)
    event = NewsEvent(
        id="event-1",
        title="Positive earnings surprise",
        source="test",
        published_at="2026-09-07T09:00:00+00:00",
        symbols=["RELIANCE"],
        materiality=0.9,
    )
    news_repository.save(event)

    result = await service.process(event.id, quantity=10, market_phase=MarketPhase.MARKET_HOURS)

    assert result.status == "EXECUTED"
    assert result.decision is not None
    assert result.intent is not None and result.intent.approved is True
    assert result.execution is not None
    assert result.execution.order.quantity == 10
    assert paper_repository.has_order_for_event(event.id)


@pytest.mark.asyncio
async def test_process_is_idempotent_for_existing_paper_order(tmp_path: Path) -> None:
    service, news_repository, paper_repository = build_service(tmp_path)
    event = NewsEvent(
        id="event-2",
        title="Positive earnings surprise",
        source="test",
        published_at="2026-09-07T09:00:00+00:00",
        symbols=["RELIANCE"],
        materiality=0.9,
    )
    news_repository.save(event)

    first = await service.process(event.id)
    second = await service.process(event.id)

    assert first.status == "EXECUTED"
    assert second.status == "ALREADY_EXECUTED"
    assert second.execution is None
    assert len(paper_repository.list_orders()) == 1
