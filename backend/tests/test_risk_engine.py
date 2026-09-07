import pytest

from app.domain.models import AiDecision, MarketPhase, NewsEvent, Signal
from app.providers.stub_market_data import StubMarketDataProvider
from app.services.risk_engine import RiskConfig, RiskEngine


def event(event_id: str = "event-1", materiality: float = 0.8, symbols: list[str] | None = None) -> NewsEvent:
    return NewsEvent(
        id=event_id,
        title="Material company update",
        source="test",
        published_at="2026-09-07T09:00:00+00:00",
        symbols=symbols if symbols is not None else ["RELIANCE"],
        materiality=materiality,
    )


def decision(signal: Signal = Signal.BUY, confidence: float = 0.8) -> AiDecision:
    return AiDecision(
        signal=signal,
        confidence=confidence,
        reasoning="Test reasoning",
        prompt_version="news-impact-v1",
        model="test",
    )


@pytest.mark.asyncio
async def test_risk_engine_approves_valid_trade() -> None:
    engine = RiskEngine(StubMarketDataProvider())
    result = await engine.evaluate(event(), decision(), quantity=10)
    assert result.approved is True
    assert result.symbol == "RELIANCE"
    assert result.entry_price == 1_500.0
    assert result.notional == 15_000.0
    assert result.quantity == 10


@pytest.mark.asyncio
async def test_risk_engine_rejects_non_market_hours() -> None:
    engine = RiskEngine(StubMarketDataProvider())
    result = await engine.evaluate(event(), decision(), market_phase=MarketPhase.PRE_MARKET)
    assert result.approved is False
    assert "market phase" in result.reason


@pytest.mark.asyncio
async def test_risk_engine_rejects_duplicate_event() -> None:
    engine = RiskEngine(StubMarketDataProvider())
    first = await engine.evaluate(event(), decision())
    second = await engine.evaluate(event(), decision())
    assert first.approved is True
    assert second.approved is False
    assert "duplicate" in second.reason


@pytest.mark.asyncio
async def test_risk_engine_rejects_missing_price() -> None:
    engine = RiskEngine(StubMarketDataProvider())
    result = await engine.evaluate(event(symbols=["INFY"]), decision())
    assert result.approved is False
    assert "market price" in result.reason


@pytest.mark.asyncio
async def test_risk_engine_rejects_excess_notional() -> None:
    engine = RiskEngine(StubMarketDataProvider(), RiskConfig(max_order_notional=1_000.0))
    result = await engine.evaluate(event(), decision(), quantity=1)
    assert result.approved is False
    assert "notional" in result.reason
