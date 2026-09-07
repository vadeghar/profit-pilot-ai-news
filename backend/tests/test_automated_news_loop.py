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
        return ProcessingResult(status="REJECTED", event=NewsEvent(id=event_id, title="t", source="s", published_at="2026-09-07T00:00:00Z"), reason="test")


@pytest.mark.asyncio
async def test_run_once_ingests_and_processes_new_events() -> None:
    events = [NewsEvent(id="e1", title="One", source="test", published_at="2026-09-07T00:00:00Z")]
    ingestion = FakeIngestion(events)
    processing = FakeProcessing()
    loop = AutomatedNewsLoop(ingestion, processing, interval_seconds=60, quantity=3)

    assert await loop.run_once() == 1
    assert ingestion.calls == 1
    assert processing.calls == [("e1", 3, MarketPhase.MARKET_HOURS)]


def test_loop_validates_configuration() -> None:
    ingestion = FakeIngestion([])
    processing = FakeProcessing()
    with pytest.raises(ValueError):
        AutomatedNewsLoop(ingestion, processing, interval_seconds=0)
    with pytest.raises(ValueError):
        AutomatedNewsLoop(ingestion, processing, quantity=0)
