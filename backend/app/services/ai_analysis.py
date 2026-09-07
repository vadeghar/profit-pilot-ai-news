import json

from app.domain.models import AiDecision, NewsEvent
from app.providers.interfaces import LlmProvider
from app.services.entity_resolution import CompanyEntityResolver
from app.services.prompt_builder import build_news_impact_prompt
from app.services.source_reliability import SourceReliabilityRegistry
from app.storage import AiDecisionRepository, NewsEventRepository


class AiAnalysisService:
    def __init__(
        self,
        news_repository: NewsEventRepository,
        decision_repository: AiDecisionRepository,
        llm_provider: LlmProvider,
        *,
        entity_resolver: CompanyEntityResolver | None = None,
        source_reliability: SourceReliabilityRegistry | None = None,
    ) -> None:
        self.news_repository = news_repository
        self.decision_repository = decision_repository
        self.llm_provider = llm_provider
        self.entity_resolver = entity_resolver
        self.source_reliability = source_reliability

    async def analyze(self, event_id: str) -> AiDecision:
        event = self.news_repository.get(event_id)
        if event is None:
            raise ValueError(f"News event not found: {event_id}")

        prompt = build_news_impact_prompt(
            event,
            resolver=self.entity_resolver,
            source_reliability=self.source_reliability,
        )
        decision = await self.llm_provider.analyze(event, prompt)

        entities = self.entity_resolver.resolve(event.title) if self.entity_resolver else []
        reliability = self.source_reliability.evaluate(event.source) if self.source_reliability else None
        input_snapshot = json.dumps(
            {
                "event": event.model_dump(mode="json"),
                "resolved_entities": [match.__dict__ for match in entities],
                "source_reliability": reliability.__dict__ if reliability else None,
            },
            sort_keys=True,
        )
        self.decision_repository.save(event.id, decision, prompt, input_snapshot)
        return decision

    def decisions_for_event(self, event_id: str) -> list[AiDecision]:
        return self.decision_repository.list_for_event(event_id)
