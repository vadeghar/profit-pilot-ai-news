import logging

from app.domain.models import AiDecision, NewsEvent
from app.providers.interfaces import LlmProvider

logger = logging.getLogger(__name__)


class FallbackLlmProvider(LlmProvider):
    """Use the primary LLM first and fall back to a secondary provider on failure."""

    def __init__(self, primary: LlmProvider, fallback: LlmProvider | None = None) -> None:
        self.primary = primary
        self.fallback = fallback

    async def analyze(self, event: NewsEvent, prompt: str) -> AiDecision:
        try:
            return await self.primary.analyze(event, prompt)
        except Exception as primary_error:
            if self.fallback is None:
                logger.error(
                    "Primary LLM failed for event %s and no fallback provider is configured: %s",
                    event.id,
                    primary_error,
                )
                raise
            logger.warning(
                "Primary LLM failed for event %s; using fallback provider: %s",
                event.id,
                primary_error,
            )
            return await self.fallback.analyze(event, prompt)
