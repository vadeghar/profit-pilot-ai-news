from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.config import settings
from app.domain.models import MarketBrainSnapshot


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.environment}


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
