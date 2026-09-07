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
            resolved = self.entity_resolution.enrich(event)
            self.repository.save(resolved)
            enriched.append(resolved)
        return enriched
