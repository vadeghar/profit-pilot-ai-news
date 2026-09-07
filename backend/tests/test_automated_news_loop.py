import pytest

from app.domain.models import MarketPhase, NewsEvent, ProcessingResult
from app.services.automated_news_loop import AutomatedNewsLoop


class FakeIngestion:
    def __init__(self, events: list[NewsEvent]) -> None:
        self.events = events
        self.calls = 0

    async def ingest_new(self) -> list[NewsEvent]:
        self.calls += 1
        return self.events


class FakeProcessing:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, MarketPhase]] = []

    async def process(self, event_id: str, *, quantity: int, market_phase: MarketPhase) -> ProcessingResult:
        self.calls.append((event_id, quantity, market_phase))
        return ProcessingResult(
            status="REJECTED",
            event=NewsEvent(id=event_id, title="t", source="s", published_at="2026-09-07T00:00:00Z"),
            reason="test",
        )


class FakeQueue:
    def __init__(self) -> None:
        self.items: dict[str, str] = {}
        self.enqueued: list[str] = []

    def enqueue(self, event_id: str, priority: float) -> None:
        self.enqueued.append(event_id)
        self.items.setdefault(event_id, "PENDING")

    def pending_count(self) -> int:
        return sum(status in {"PENDING", "FAILED"} for status in self.items.values())

    def list_due(self, limit: int = 5) -> list[str]:
        return [event_id for event_id, status in self.items.items() if status in {"PENDING", "FAILED"}][:limit]

    def mark_processing(self, event_id: str) -> None:
        self.items[event_id] = "PROCESSING"

    def mark_completed(self, event_id: str) -> None:
        self.items[event_id] = "COMPLETED"

    def mark_failed(self, event_id: str, error: str, retry_after_seconds: int = 60) -> None:
        self.items[event_id] = "FAILED"


@pytest.mark.asyncio
async def test_post_market_processes_queue_only_on_first_due_cycle() -> None:
    events = [NewsEvent(id="e1", title="One", source="test", published_at="2026-09-07T00:00:00Z")]
    ingestion = FakeIngestion(events)
    processing = FakeProcessing()
    queue = FakeQueue()
    loop = AutomatedNewsLoop(
        ingestion,
        processing,
        queue_repository=queue,
        interval_seconds=60,
        quantity=3,
        phase_provider=lambda: MarketPhase.POST_MARKET,
        post_market_ai_interval_seconds=1800,
    )

    assert await loop.run_once() == 1
    assert await loop.run_once() == 0
    assert ingestion.calls == 2
    assert processing.calls == [("e1", 3, MarketPhase.POST_MARKET)]
    assert queue.enqueued == ["e1", "e1"]


@pytest.mark.asyncio
async def test_live_phase_processes_pending_queue() -> None:
    events = [NewsEvent(id="e1", title="One", source="test", published_at="2026-09-07T00:00:00Z")]
    ingestion = FakeIngestion(events)
    processing = FakeProcessing()
    queue = FakeQueue()
    loop = AutomatedNewsLoop(
        ingestion,
        processing,
        queue_repository=queue,
        interval_seconds=60,
        quantity=1,
        phase_provider=lambda: MarketPhase.MARKET_HOURS,
        market_hours_ai_interval_seconds=15,
    )

    assert await loop.run_once() == 1
    assert processing.calls == [("e1", 1, MarketPhase.MARKET_HOURS)]


def test_loop_validates_configuration() -> None:
    ingestion = FakeIngestion([])
    processing = FakeProcessing()
    queue = FakeQueue()
    with pytest.raises(ValueError):
        AutomatedNewsLoop(ingestion, processing, queue_repository=queue, interval_seconds=0)
    with pytest.raises(ValueError):
        AutomatedNewsLoop(ingestion, processing, queue_repository=queue, quantity=0)
