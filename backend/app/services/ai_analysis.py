import json

from app.domain.models import AiDecision, NewsEvent
from app.providers.interfaces import LlmProvider
from app.services.prompt_builder import build_news_impact_prompt
from app.storage import AiDecisionRepository, NewsEventRepository


class AiAnalysisService:
    def __init__(
        self,
        news_repository: NewsEventRepository,
        decision_repository: AiDecisionRepository,
        llm_provider: LlmProvider,
    ) -> None:
        self.news_repository = news_repository
        self.decision_repository = decision_repository
        self.llm_provider = llm_provider

    async def analyze(self, event_id: str) -> AiDecision:
        event = self.news_repository.get(event_id)
        if event is None:
            raise ValueError(f"News event not found: {event_id}")

        prompt = build_news_impact_prompt(event)
        decision = await self.llm_provider.analyze(event, prompt)
        input_snapshot = json.dumps(event.model_dump(mode="json"), sort_keys=True)
        self.decision_repository.save(event.id, decision, prompt, input_snapshot)
        return decision

    def decisions_for_event(self, event_id: str) -> list[AiDecision]:
        return self.decision_repository.list_for_event(event_id)
