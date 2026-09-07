import pytest

from app.domain.models import NewsEvent
from app.services.news_ingestion import NewsIngestionService


class FakeProvider:
    def __init__(self, events: list[NewsEvent]) -> None:
        self.events = events

    async def fetch(self) -> list[NewsEvent]:
        return self.events


class FakeRepository:
    def __init__(self, existing: set[str] | None = None) -> None:
        self.existing = existing or set()
        self.saved: list[str] = []

    def exists(self, event_id: str) -> bool:
        return event_id in self.existing

    def save(self, event: NewsEvent) -> None:
        self.existing.add(event.id)
        self.saved.append(event.id)


@pytest.mark.asyncio
async def test_ingest_new_returns_only_unseen_events() -> None:
    events = [
        NewsEvent(id="existing", title="Old", source="test", published_at="2026-09-07T08:00:00Z"),
        NewsEvent(id="new", title="New", source="test", published_at="2026-09-07T09:00:00Z"),
    ]
    repository = FakeRepository({"existing"})
    service = NewsIngestionService(FakeProvider(events), repository)

    result = await service.ingest_new()

    assert [event.id for event in result] == ["new"]
    assert repository.saved == ["existing", "new"]
