from app.domain.models import AiDecision, NewsEvent, Signal


class StubLlmProvider:
    async def analyze(self, event: NewsEvent, prompt: str) -> AiDecision:
        return AiDecision(
            signal=Signal.IGNORE,
            confidence=0.0,
            reasoning="Stub provider: no model configured.",
            prompt_version="v1",
            model="stub",
        )
