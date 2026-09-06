from app.domain.models import AiDecision, NewsEvent
from app.providers.interfaces import LlmProvider


class StubLlmProvider(LlmProvider):
    async def analyze(self, event: NewsEvent, prompt: str) -> AiDecision:
        return AiDecision(
            signal="IGNORE",
            confidence=0.0,
            reasoning="Stub provider: no real LLM is configured; no trading signal is produced.",
            prompt_version="news-impact-v1",
            model="stub",
        )
