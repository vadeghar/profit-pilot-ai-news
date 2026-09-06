from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.config import settings
from app.domain.models import MarketBrainSnapshot, NewsEvent
from app.providers.stub_news import StubNewsProvider
from app.services.news_ingestion import NewsIngestionService
from app.storage import NewsEventRepository, SqliteDatabase


database = SqliteDatabase(settings.database_url)
news_repository = NewsEventRepository(database)
news_provider = StubNewsProvider()
news_ingestion = NewsIngestionService(news_provider, news_repository)


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
