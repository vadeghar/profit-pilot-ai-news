from datetime import datetime, timezone

from app.domain.models import NewsEvent
from app.providers.interfaces import NewsProvider


class StubNewsProvider(NewsProvider):
    async def fetch(self) -> list[NewsEvent]:
        now = datetime.now(timezone.utc).isoformat()
        return [
            NewsEvent(
                id="stub-reliance-001",
                title="Reliance Industries announces a new strategic initiative",
                source="stub-news",
                published_at=now,
                symbols=["RELIANCE"],
                materiality=0.7,
            ),
            NewsEvent(
                id="stub-tcs-001",
                title="TCS reports a technology services update",
                source="stub-news",
                published_at=now,
                symbols=["TCS"],
                materiality=0.5,
            ),
        ]
