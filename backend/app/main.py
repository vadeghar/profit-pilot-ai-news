from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from app.config import settings
from app.domain.models import AiDecision, MarketBrainSnapshot, MarketPhase, NewsEvent, PaperExecutionResult, PaperOrder, PositionSnapshot, ProcessingResult, TradeIntent
from app.providers.angel_one import AngelOneMarketDataProvider
from app.providers.rss_news import RssNewsProvider
from app.providers.stub_llm import StubLlmProvider
from app.providers.stub_market_data import StubMarketDataProvider
from app.providers.stub_news import StubNewsProvider
from app.services.ai_analysis import AiAnalysisService
from app.services.automated_news_loop import AutomatedNewsLoop
from app.services.entity_catalog import resolver
from app.services.event_processing import EventProcessingService
from app.services.market_brain import MarketBrainService
from app.services.market_phase import current_market_phase
from app.services.news_ingestion import NewsIngestionService
from app.services.paper_trading import PaperTradingService
from app.services.portfolio import PortfolioService
from app.services.risk_engine import RiskConfig, RiskEngine
from app.services.source_reliability import SourceReliabilityRegistry
from app.storage import AiDecisionRepository, NewsEventRepository, PaperTradingRepository, SqliteDatabase


database = SqliteDatabase(settings.database_url)
news_repository = NewsEventRepository(database)
decision_repository = AiDecisionRepository(database)
paper_repository = PaperTradingRepository(database)
source_reliability = SourceReliabilityRegistry()

if settings.news_provider.lower() == "rss":
    news_provider = RssNewsProvider(settings.news_feeds, resolver=resolver, symbol_keywords=settings.news_symbol_keywords, timeout_seconds=settings.news_fetch_timeout_seconds, max_items_per_feed=settings.news_max_items_per_feed)
else:
    news_provider = StubNewsProvider()

llm_provider = StubLlmProvider()

if settings.market_data_provider.lower() == "angel_one":
    market_data_provider = AngelOneMarketDataProvider(api_key=settings.angel_api_key, client_code=settings.angel_client_code, password=settings.angel_password, totp_secret=settings.angel_totp_secret, symbol_tokens=settings.angel_symbol_tokens, exchange=settings.angel_exchange)
else:
    market_data_provider = StubMarketDataProvider()

news_ingestion = NewsIngestionService(news_provider, news_repository)
ai_analysis = AiAnalysisService(news_repository, decision_repository, llm_provider, entity_resolver=resolver, source_reliability=source_reliability)
risk_engine = RiskEngine(market_data_provider, RiskConfig(max_order_notional=settings.max_order_notional, max_order_quantity=settings.max_order_quantity))
paper_trading = PaperTradingService(paper_repository)
portfolio = PortfolioService(paper_repository, market_data_provider)
event_processing = EventProcessingService(news_repository, ai_analysis, risk_engine, paper_trading, paper_repository)
market_brain = MarketBrainService(news_repository, decision_repository, paper_repository, portfolio)


class MarketBrainConnectionManager:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self) -> None:
        if not self.connections:
            return
        payload = (await market_brain.snapshot()).model_dump(mode="json")
        stale: list[WebSocket] = []
        for websocket in self.connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(websocket)


brain_connections = MarketBrainConnectionManager()


async def _broadcast_brain() -> None:
    await brain_connections.broadcast()


def _market_phase() -> MarketPhase:
    return current_market_phase()


news_loop = AutomatedNewsLoop(
    news_ingestion,
    event_processing,
    interval_seconds=settings.news_poll_interval_seconds,
    quantity=settings.news_trade_quantity,
    phase_provider=_market_phase,
    on_update=_broadcast_brain,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.initialize()
    if settings.news_provider.lower() == "rss" and settings.news_feeds:
        news_loop.start()
    yield
    await news_loop.stop()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment, "database": "ok" if database.check() else "error", "market_data_provider": settings.market_data_provider, "news_provider": settings.news_provider, "news_loop": "running" if news_loop.running else "stopped"}


@app.post("/api/v1/news/ingest", response_model=list[NewsEvent])
async def ingest_news() -> list[NewsEvent]:
    events = await news_ingestion.ingest()
    await brain_connections.broadcast()
    return events


@app.get("/api/v1/news", response_model=list[NewsEvent])
async def list_news(limit: int = 50) -> list[NewsEvent]:
    if limit < 1 or limit > 200:
        limit = 50
    return news_repository.list_recent(limit)


@app.post("/api/v1/news/{event_id}/analyze", response_model=AiDecision)
async def analyze_news(event_id: str) -> AiDecision:
    try:
        decision = await ai_analysis.analyze(event_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await brain_connections.broadcast()
    return decision


@app.get("/api/v1/news/{event_id}/decisions", response_model=list[AiDecision])
async def list_ai_decisions(event_id: str) -> list[AiDecision]:
    if news_repository.get(event_id) is None:
        raise HTTPException(status_code=404, detail=f"News event not found: {event_id}")
    return ai_analysis.decisions_for_event(event_id)


@app.post("/api/v1/news/{event_id}/process", response_model=ProcessingResult)
async def process_news_event(event_id: str, quantity: int = 1, market_phase: MarketPhase = MarketPhase.MARKET_HOURS) -> ProcessingResult:
    try:
        result = await event_processing.process(event_id, quantity=quantity, market_phase=market_phase)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await brain_connections.broadcast()
    return result


@app.post("/api/v1/news/{event_id}/trade-intent", response_model=TradeIntent)
async def create_trade_intent(event_id: str, quantity: int = 1, market_phase: MarketPhase = MarketPhase.MARKET_HOURS) -> TradeIntent:
    event = news_repository.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"News event not found: {event_id}")
    decisions = ai_analysis.decisions_for_event(event_id)
    if not decisions:
        raise HTTPException(status_code=409, detail="Analyze the news event before creating a trade intent.")
    intent = await risk_engine.evaluate(event, decisions[0], quantity=quantity, market_phase=market_phase)
    await brain_connections.broadcast()
    return intent


@app.post("/api/v1/trade-intents/execute", response_model=PaperExecutionResult)
async def execute_trade_intent(intent: TradeIntent) -> PaperExecutionResult:
    try:
        result = paper_trading.execute(intent)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await brain_connections.broadcast()
    return result


@app.get("/api/v1/paper/orders", response_model=list[PaperOrder])
async def list_paper_orders(limit: int = 50) -> list[PaperOrder]:
    if limit < 1 or limit > 200:
        limit = 50
    return paper_repository.list_orders(limit)


@app.get("/api/v1/paper/positions", response_model=list[PositionSnapshot])
async def list_paper_positions() -> list[PositionSnapshot]:
    return await portfolio.snapshots()


@app.get("/api/v1/market-brain/snapshot", response_model=MarketBrainSnapshot)
async def market_brain_snapshot() -> MarketBrainSnapshot:
    return await market_brain.snapshot()


@app.websocket("/ws/market-brain")
async def market_brain_socket(websocket: WebSocket) -> None:
    await brain_connections.connect(websocket)
    try:
        await websocket.send_json((await market_brain.snapshot()).model_dump(mode="json"))
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        brain_connections.disconnect(websocket)
