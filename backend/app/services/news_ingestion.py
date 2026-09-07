from app.domain.models import NewsEvent
from app.providers.interfaces import NewsProvider
from app.services.entity_resolution import EntityResolutionService
from app.storage import NewsEventRepository


class NewsIngestionService:
    def __init__(
        self,
        provider: NewsProvider,
        repository: NewsEventRepository,
        entity_resolution: EntityResolutionService | None = None,
    ) -> None:
        self.provider = provider
        self.repository = repository
        self.entity_resolution = entity_resolution or EntityResolutionService.default()

    async def ingest(self) -> list[NewsEvent]:
        events = await self.provider.fetch()
        enriched: list[NewsEvent] = []
        for event in events:
            self.repository.save(event)
        return events

    async def ingest_new(self) -> list[NewsEvent]:
        """Persist fetched events and return only events not seen before."""
        events = await self.provider.fetch()
        new_events: list[NewsEvent] = []
        for event in events:
            is_new = not self.repository.exists(event.id)
            self.repository.save(event)
            if is_new:
                new_events.append(event)
        return new_events
