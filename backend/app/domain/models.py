from enum import StrEnum

from pydantic import BaseModel, Field


class MarketPhase(StrEnum):
    PRE_MARKET = "PRE_MARKET"
    MARKET_HOURS = "MARKET_HOURS"
    POST_MARKET = "POST_MARKET"


class Signal(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    IGNORE = "IGNORE"


class NewsEvent(BaseModel):
    id: str
    title: str
    source: str
    published_at: str
    symbols: list[str] = Field(default_factory=list)
    materiality: float = Field(ge=0, le=1, default=0)


class AiDecision(BaseModel):
    signal: Signal
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    prompt_version: str
    model: str


class TradeIntent(BaseModel):
    event_id: str
    symbol: str
    side: Signal
    quantity: int = Field(ge=0)
    entry_price: float = Field(ge=0)
    notional: float = Field(ge=0)
    approved: bool
    reason: str
    rule_version: str


class MarketBrainNode(BaseModel):
    id: str
    kind: str
    label: str
    metadata: dict[str, str | float | int | bool] = Field(default_factory=dict)


class MarketBrainEdge(BaseModel):
    source: str
    target: str
    relation: str


class MarketBrainSnapshot(BaseModel):
    phase: MarketPhase
    nodes: list[MarketBrainNode]
    edges: list[MarketBrainEdge]

    @classmethod
    def empty(cls) -> "MarketBrainSnapshot":
        return cls(phase=MarketPhase.PRE_MARKET, nodes=[], edges=[])
