from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from app.domain.models import MarketPhase, NewsEvent
from app.services.event_processing import EventProcessingService
from app.services.news_ingestion import NewsIngestionService
from app.storage import AiQueueRepository

logger = logging.getLogger(__name__)


class AutomatedNewsLoop:
    """Ingest continuously and process the persistent AI queue according to market phase."""

    def __init__(
        self,
        ingestion: NewsIngestionService,
        processing: EventProcessingService,
        *,
        queue_repository: AiQueueRepository,
        interval_seconds: float = 60.0,
        quantity: int = 1,
        phase_provider: Callable[[], MarketPhase] | None = None,
        on_update: Callable[[], Awaitable[None]] | None = None,
        post_market_ai_interval_seconds: float = 1800.0,
        pre_market_ai_interval_seconds: float = 60.0,
        market_hours_ai_interval_seconds: float = 15.0,
        max_ai_events_per_cycle: int = 5,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if post_market_ai_interval_seconds <= 0:
            raise ValueError("post_market_ai_interval_seconds must be greater than zero")
        if pre_market_ai_interval_seconds <= 0:
            raise ValueError("pre_market_ai_interval_seconds must be greater than zero")
        if market_hours_ai_interval_seconds <= 0:
            raise ValueError("market_hours_ai_interval_seconds must be greater than zero")
        if max_ai_events_per_cycle <= 0:
            raise ValueError("max_ai_events_per_cycle must be greater than zero")

        self.ingestion = ingestion
        self.processing = processing
        self.queue_repository = queue_repository
        self.interval_seconds = interval_seconds
        self.quantity = quantity
        self.phase_provider = phase_provider or (lambda: MarketPhase.MARKET_HOURS)
        self.on_update = on_update
        self.post_market_ai_interval_seconds = post_market_ai_interval_seconds
        self.pre_market_ai_interval_seconds = pre_market_ai_interval_seconds
        self.market_hours_ai_interval_seconds = market_hours_ai_interval_seconds
        self.max_ai_events_per_cycle = max_ai_events_per_cycle
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self.last_cycle_at: str | None = None
        self.last_cycle_new = 0
        self.last_cycle_processed = 0
        self.last_cycle_error: str | None = None
        self.last_ai_run_at: str | None = None
        self.last_ai_phase: MarketPhase | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def _ai_interval(self, phase: MarketPhase) -> float:
        if phase == MarketPhase.POST_MARKET:
            return self.post_market_ai_interval_seconds
        if phase == MarketPhase.PRE_MARKET:
            return self.pre_market_ai_interval_seconds
        return self.market_hours_ai_interval_seconds

    def _ai_due(self, phase: MarketPhase, now: datetime) -> bool:
        if self.last_ai_run_at is None:
            return True
        try:
            last_run = datetime.fromisoformat(self.last_ai_run_at)
        except ValueError:
            return True
        return now >= last_run + timedelta(seconds=self._ai_interval(phase))

    @staticmethod
    def _priority(event: NewsEvent) -> float:
        return min(1.0, event.materiality + min(len(event.symbols), 3) * 0.1)

    async def run_once(self) -> int:
        self.last_cycle_at = datetime.now().astimezone().isoformat()
        self.last_cycle_error = None
        events = await self.ingestion.ingest_new()
        self.last_cycle_new = len(events)

        for event in events:
            self.queue_repository.enqueue(event.id, self._priority(event))

        phase = self.phase_provider()
        now = datetime.now().astimezone()
        processed = 0

        if self._ai_due(phase, now) and self.queue_repository.pending_count() > 0:
            event_ids = self.queue_repository.list_due(limit=self.max_ai_events_per_cycle)
            for event_id in event_ids:
                self.queue_repository.mark_processing(event_id)
                try:
                    await self.processing.process(
                        event_id,
                        quantity=self.quantity,
                        market_phase=phase,
                    )
                    self.queue_repository.mark_completed(event_id)
                    processed += 1
                except Exception as exc:
                    self.queue_repository.mark_failed(
                        event_id,
                        str(exc),
                        retry_after_seconds=max(30, int(self._ai_interval(phase))),
                    )
                    self.last_cycle_error = str(exc)
                    logger.exception("Failed to process queued news event %s", event_id)

            if event_ids:
                self.last_ai_run_at = datetime.now().astimezone().isoformat()
                self.last_ai_phase = phase

        self.last_cycle_processed = processed
        if events and self.on_update is not None:
            await self.on_update()
        return processed

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_cycle_at = datetime.now().astimezone().isoformat()
                self.last_cycle_error = str(exc)
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
