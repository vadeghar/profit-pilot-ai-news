from app.domain.models import AiDecision, NewsEvent, Signal
from app.services.trading_rules import evaluate_trading_signal


def event(materiality: float = 0.8, symbols: list[str] | None = None) -> NewsEvent:
    return NewsEvent(
        id="event-1",
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


def test_approved_signal_passes_rules() -> None:
    result = evaluate_trading_signal(event(), decision())
    assert result.approved is True
    assert result.symbol == "RELIANCE"
    assert result.signal == Signal.BUY
    assert result.rule_version == "trading-rules-v1"


def test_ignore_signal_is_not_tradeable() -> None:
    result = evaluate_trading_signal(event(), decision(Signal.IGNORE))
    assert result.approved is False
    assert result.signal == Signal.IGNORE


def test_low_materiality_is_rejected() -> None:
    result = evaluate_trading_signal(event(materiality=0.59), decision())
    assert result.approved is False
    assert "materiality" in result.reason


def test_low_confidence_is_rejected() -> None:
    result = evaluate_trading_signal(event(), decision(confidence=0.64))
    assert result.approved is False
    assert "confidence" in result.reason


def test_missing_symbol_is_rejected() -> None:
    result = evaluate_trading_signal(event(symbols=[]), decision())
    assert result.approved is False
    assert result.symbol is None
