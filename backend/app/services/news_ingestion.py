from app.domain.models import NewsEvent
from app.providers.interfaces import NewsProvider
from app.storage import NewsEventRepository


class NewsIngestionService:
    def __init__(self, provider: NewsProvider, repository: NewsEventRepository) -> None:
        self.provider = provider
        self.repository = repository

    async def ingest(self) -> list[NewsEvent]:
        events = await self.provider.fetch()
        for event in events:
            self.repository.save(event)
        return events
