from abc import ABC, abstractmethod

from app.domain.models import AiDecision, NewsEvent


class NewsProvider(ABC):
    @abstractmethod
    async def fetch(self) -> list[NewsEvent]:
        raise NotImplementedError


class LlmProvider(ABC):
    @abstractmethod
    async def analyze(self, event: NewsEvent, prompt: str) -> AiDecision:
        raise NotImplementedError


class MarketDataProvider(ABC):
    @abstractmethod
    async def last_price(self, symbol: str) -> float | None:
        raise NotImplementedError


class ExecutionProvider(ABC):
    @abstractmethod
    async def place_paper_order(self, symbol: str, side: str, quantity: int) -> str:
        raise NotImplementedError
