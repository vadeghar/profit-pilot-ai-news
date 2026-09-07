import asyncio
import json
import random

import httpx

from app.domain.models import AiDecision, NewsEvent, Signal
from app.providers.interfaces import LlmProvider
from app.services.prompt_builder import PROMPT_VERSION


class GroqLlmProvider(LlmProvider):
    """Groq provider using its OpenAI-compatible Chat Completions API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
        retry_base_seconds: float = 1.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.retry_base_seconds = max(0.1, retry_base_seconds)

    def _response_format(self) -> dict[str, object]:
        if self.model in {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}:
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": "news_impact_decision",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "signal": {"type": "string", "enum": ["BUY", "SELL", "IGNORE"]},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "reasoning": {"type": "string"},
                        },
                        "required": ["signal", "confidence", "reasoning"],
                        "additionalProperties": False,
                    },
                },
            }
        return {"type": "json_object"}

    def _delay_for_response(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return max(0.1, float(retry_after))
            except ValueError:
                pass
        return self.retry_base_seconds * (2**attempt) + random.uniform(0, self.retry_base_seconds)

    async def analyze(self, event: NewsEvent, prompt: str) -> AiDecision:
        payload: dict[str, object] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only the requested structured JSON decision. "
                        "signal must be BUY, SELL, or IGNORE. "
                        "confidence must be a number from 0 to 1."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": self._response_format(),
            "temperature": 0.1,
            "stream": False,
        }
        if self.model in {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}:
            payload["reasoning_effort"] = "low"

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    break
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = exc.response.status_code
                if status not in {408, 429} and not 500 <= status <= 599:
                    raise RuntimeError(f"Groq request failed: {exc}") from exc
                if attempt >= self.max_retries:
                    raise RuntimeError(f"Groq request failed after retries: {exc}") from exc
                await asyncio.sleep(self._delay_for_response(exc.response, attempt))
            except httpx.RequestError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise RuntimeError(f"Groq request failed after retries: {exc}") from exc
                await asyncio.sleep(
                    self.retry_base_seconds * (2**attempt)
                    + random.uniform(0, self.retry_base_seconds)
                )
        else:
            raise RuntimeError(f"Groq request failed: {last_error}") from last_error

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
            raise RuntimeError("Groq returned an invalid AI decision payload") from exc

        return AiDecision(
            signal=signal,
            confidence=confidence,
            reasoning=reasoning,
            prompt_version=PROMPT_VERSION,
            model=self.model,
        )
