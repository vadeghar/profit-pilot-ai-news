from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.domain.models import MarketPhase
from app.services.event_processing import EventProcessingService
from app.services.news_ingestion import NewsIngestionService

logger = logging.getLogger(__name__)


class AutomatedNewsLoop:
    """Periodically ingest and process newly discovered news events."""

    def __init__(
        self,
        ingestion: NewsIngestionService,
        processing: EventProcessingService,
        *,
        interval_seconds: float = 300.0,
        quantity: int = 1,
        phase_provider: Callable[[], MarketPhase] | None = None,
        on_update: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        self.ingestion = ingestion
        self.processing = processing
        self.interval_seconds = interval_seconds
        self.quantity = quantity
        self.phase_provider = phase_provider or (lambda: MarketPhase.MARKET_HOURS)
        self.on_update = on_update
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def run_once(self) -> int:
        events = await self.ingestion.ingest()
        phase = self.phase_provider()
        processed = 0
        for event in events:
            try:
                await self.processing.process(event.id, quantity=self.quantity, market_phase=phase)
                processed += 1
            except Exception:
                logger.exception("Failed to process news event %s", event.id)
        if events and self.on_update is not None:
            await self.on_update()
        return processed

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Automated news intelligence cycle failed")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                continue

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="automated-news-loop")

    async def stop(self) -> None:
        task = self._task
        if task is None:
            return
        self._stop.set()
        await task
        self._task = None
