from app.domain.models import AiDecision, NewsEvent
from app.providers.interfaces import LlmProvider
from app.services.prompt_builder import PROMPT_VERSION


class StubLlmProvider(LlmProvider):
    async def analyze(self, event: NewsEvent, prompt: str) -> AiDecision:
        return AiDecision(
            signal="IGNORE",
            confidence=0.0,
            reasoning="Stub provider: no real LLM is configured; no trading signal is produced.",
            prompt_version=PROMPT_VERSION,
            model="stub",
        )
