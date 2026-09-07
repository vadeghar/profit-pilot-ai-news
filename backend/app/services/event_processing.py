from app.domain.models import (
    AiDecision,
    MarketPhase,
    PaperExecutionResult,
    ProcessingResult,
    TradeIntent,
)
from app.services.ai_analysis import AiAnalysisService
from app.services.paper_trading import PaperTradingService
from app.services.risk_engine import RiskEngine
from app.storage import NewsEventRepository, PaperTradingRepository


class EventProcessingService:
    """Orchestrates analysis, deterministic rules, risk checks, and paper execution."""

    def __init__(
        self,
        news_repository: NewsEventRepository,
        decision_service: AiAnalysisService,
        risk_engine: RiskEngine,
        paper_trading: PaperTradingService,
        paper_repository: PaperTradingRepository,
    ) -> None:
        self.news_repository = news_repository
        self.decision_service = decision_service
        self.risk_engine = risk_engine
        self.paper_trading = paper_trading
        self.paper_repository = paper_repository

    async def process(
        self,
        event_id: str,
        *,
        quantity: int = 1,
        market_phase: MarketPhase = MarketPhase.MARKET_HOURS,
    ) -> ProcessingResult:
        event = self.news_repository.get(event_id)
        if event is None:
            raise ValueError(f"News event not found: {event_id}")

        decisions = self.decision_service.decisions_for_event(event_id)
        decision: AiDecision
        if decisions:
            decision = decisions[0]
        else:
            decision = await self.decision_service.analyze(event_id)

        intent: TradeIntent = await self.risk_engine.evaluate(
            event,
            decision,
            quantity=quantity,
            market_phase=market_phase,
        )

        if not intent.approved:
            return ProcessingResult(
                status="REJECTED",
                event=event,
                decision=decision,
                intent=intent,
                reason=intent.reason,
            )

        if self.paper_repository.has_order_for_event(event_id):
            return ProcessingResult(
                status="ALREADY_EXECUTED",
                event=event,
                decision=decision,
                intent=intent,
                reason="A paper order already exists for this news event.",
            )

        execution: PaperExecutionResult = self.paper_trading.execute(intent)
        return ProcessingResult(
            status="EXECUTED",
            event=event,
            decision=decision,
            intent=intent,
            execution=execution,
            reason="News event processed and paper trade executed.",
        )
