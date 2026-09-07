from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from app.config import settings
from app.domain.models import AiDecision, MarketBrainSnapshot, MarketPhase, NewsEvent, PaperOrder, Position, TradeIntent
from app.providers.stub_llm import StubLlmProvider
from app.providers.stub_market_data import StubMarketDataProvider
from app.providers.stub_news import StubNewsProvider
from app.services.ai_analysis import AiAnalysisService
from app.services.news_ingestion import NewsIngestionService
from app.services.paper_trading import PaperExecutionResult, PaperTradingService
from app.services.risk_engine import RiskConfig, RiskEngine
from app.storage import AiDecisionRepository, NewsEventRepository, PaperTradingRepository, SqliteDatabase


database = SqliteDatabase(settings.database_url)
news_repository = NewsEventRepository(database)
decision_repository = AiDecisionRepository(database)
paper_repository = PaperTradingRepository(database)
news_provider = StubNewsProvider()
llm_provider = StubLlmProvider()
market_data_provider = StubMarketDataProvider()
news_ingestion = NewsIngestionService(news_provider, news_repository)
ai_analysis = AiAnalysisService(news_repository, decision_repository, llm_provider)
risk_engine = RiskEngine(
    market_data_provider,
    RiskConfig(
        max_order_notional=settings.max_order_notional,
        max_order_quantity=settings.max_order_quantity,
    ),
)
paper_trading = PaperTradingService(paper_repository)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.initialize()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "environment": settings.environment,
        "database": "ok" if database.check() else "error",
    }


@app.post("/api/v1/news/ingest", response_model=list[NewsEvent])
async def ingest_news() -> list[NewsEvent]:
    return await news_ingestion.ingest()


@app.get("/api/v1/news", response_model=list[NewsEvent])
async def list_news(limit: int = 50) -> list[NewsEvent]:
    if limit < 1 or limit > 200:
        limit = 50
    return news_repository.list_recent(limit)


@app.post("/api/v1/news/{event_id}/analyze", response_model=AiDecision)
async def analyze_news(event_id: str) -> AiDecision:
    try:
        return await ai_analysis.analyze(event_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/news/{event_id}/decisions", response_model=list[AiDecision])
async def list_ai_decisions(event_id: str) -> list[AiDecision]:
    if news_repository.get(event_id) is None:
        raise HTTPException(status_code=404, detail=f"News event not found: {event_id}")
    return ai_analysis.decisions_for_event(event_id)


@app.post("/api/v1/news/{event_id}/trade-intent", response_model=TradeIntent)
async def create_trade_intent(
    event_id: str,
    quantity: int = 1,
    market_phase: MarketPhase = MarketPhase.MARKET_HOURS,
) -> TradeIntent:
    event = news_repository.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"News event not found: {event_id}")
    decisions = ai_analysis.decisions_for_event(event_id)
    if not decisions:
        raise HTTPException(status_code=409, detail="Analyze the news event before creating a trade intent.")
    return await risk_engine.evaluate(event, decisions[0], quantity=quantity, market_phase=market_phase)


@app.post("/api/v1/trade-intents/execute", response_model=PaperExecutionResult)
async def execute_trade_intent(intent: TradeIntent) -> PaperExecutionResult:
    try:
        return paper_trading.execute(intent)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/v1/paper/orders", response_model=list[PaperOrder])
async def list_paper_orders(limit: int = 50) -> list[PaperOrder]:
    if limit < 1 or limit > 200:
        limit = 50
    return paper_repository.list_orders(limit)


@app.get("/api/v1/paper/positions", response_model=list[Position])
async def list_paper_positions() -> list[Position]:
    return paper_repository.list_positions()


@app.get("/api/v1/market-brain/snapshot", response_model=MarketBrainSnapshot)
async def market_brain_snapshot() -> MarketBrainSnapshot:
    return MarketBrainSnapshot.empty()


@app.websocket("/ws/market-brain")
async def market_brain_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        await websocket.send_json(MarketBrainSnapshot.empty().model_dump(mode="json"))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
