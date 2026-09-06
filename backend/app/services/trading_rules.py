from dataclasses import dataclass

from app.domain.models import AiDecision, NewsEvent, Signal

RULE_VERSION = "trading-rules-v1"


@dataclass(frozen=True)
class TradingSignal:
    event_id: str
    symbol: str | None
    signal: Signal
    approved: bool
    confidence: float
    reason: str
    rule_version: str = RULE_VERSION


def evaluate_trading_signal(
    event: NewsEvent,
    decision: AiDecision,
    *,
    min_materiality: float = 0.60,
    min_confidence: float = 0.65,
) -> TradingSignal:
    symbol = event.symbols[0] if event.symbols else None

    if not event.symbols:
        return TradingSignal(
            event_id=event.id,
            symbol=None,
            signal=Signal.IGNORE,
            approved=False,
            confidence=decision.confidence,
            reason="Rejected: no tradable symbol was identified.",
        )

    if decision.signal == Signal.IGNORE:
        return TradingSignal(
            event_id=event.id,
            symbol=symbol,
            signal=Signal.IGNORE,
            approved=False,
            confidence=decision.confidence,
            reason="Rejected: AI classified the event as IGNORE.",
        )

    if event.materiality < min_materiality:
        return TradingSignal(
            event_id=event.id,
            symbol=symbol,
            signal=Signal.IGNORE,
            approved=False,
            confidence=decision.confidence,
            reason=f"Rejected: materiality {event.materiality:.2f} is below {min_materiality:.2f}.",
        )

    if decision.confidence < min_confidence:
        return TradingSignal(
            event_id=event.id,
            symbol=symbol,
            signal=Signal.IGNORE,
            approved=False,
            confidence=decision.confidence,
            reason=f"Rejected: AI confidence {decision.confidence:.2f} is below {min_confidence:.2f}.",
        )

    return TradingSignal(
        event_id=event.id,
        symbol=symbol,
        signal=decision.signal,
        approved=True,
        confidence=decision.confidence,
        reason="Approved: AI signal passed materiality, confidence, and symbol checks.",
    )
