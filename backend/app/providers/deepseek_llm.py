import json

import httpx

from app.domain.models import AiDecision, NewsEvent, Signal
from app.providers.interfaces import LlmProvider
from app.services.prompt_builder import PROMPT_VERSION


class DeepSeekLlmProvider(LlmProvider):
    """DeepSeek fallback provider using the OpenAI-compatible Chat Completions API."""

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def analyze(self, event: NewsEvent, prompt: str) -> AiDecision:
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only valid JSON with exactly these fields: "
                        "signal, confidence, reasoning. "
                        "signal must be BUY, SELL, or IGNORE. "
                        "confidence must be a number from 0 to 1."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"DeepSeek request failed: {exc}") from exc

        try:
            text = data["choices"][0]["message"]["content"]
            result = json.loads(text)
            signal = Signal(str(result["signal"]).upper())
            confidence = float(result["confidence"])
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("confidence must be between 0 and 1")
            reasoning = str(result["reasoning"]).strip()
            if not reasoning:
                raise ValueError("reasoning cannot be empty")
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("DeepSeek returned an invalid AI decision payload") from exc

        return AiDecision(
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            prompt_version=PROMPT_VERSION,
            model=self.model,
        )
