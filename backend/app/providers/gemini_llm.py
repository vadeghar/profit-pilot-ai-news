import json

import httpx

from app.domain.models import AiDecision, NewsEvent, Signal
from app.providers.interfaces import LlmProvider
from app.services.prompt_builder import PROMPT_VERSION


class GeminiLlmProvider(LlmProvider):
    """Gemini provider using the official generateContent REST API."""

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30.0) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def analyze(self, event: NewsEvent, prompt: str) -> AiDecision:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        schema = {
            "type": "OBJECT",
            "properties": {
                "signal": {"type": "STRING", "enum": ["BUY", "SELL", "IGNORE"]},
                "confidence": {"type": "NUMBER"},
                "reasoning": {"type": "STRING"},
            },
            "required": ["signal", "confidence", "reasoning"],
        }
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    url,
                    headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Gemini request failed: {exc}") from exc

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(text)
            signal = Signal(str(result["signal"]).upper())
            confidence = float(result["confidence"])
            if not 0.0 <= confidence <= 1.0:
                raise ValueError("confidence must be between 0 and 1")
            reasoning = str(result["reasoning"]).strip()
            if not reasoning:
                raise ValueError("reasoning cannot be empty")
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("Gemini returned an invalid AI decision payload") from exc

        return AiDecision(
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            prompt_version=PROMPT_VERSION,
            model=self.model,
        )
