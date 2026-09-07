from dataclasses import dataclass

from app.domain.models import AiDecision, MarketPhase, NewsEvent, Signal, TradeIntent
from app.providers.interfaces import MarketDataProvider
from app.services.trading_rules import evaluate_trading_signal

RISK_VERSION = "risk-engine-v1"


@dataclass(frozen=True)
class RiskConfig:
    max_order_notional: float = 100_000.0
    max_order_quantity: int = 1_000
    allowed_market_phases: frozenset[MarketPhase] = frozenset({MarketPhase.MARKET_HOURS})


class RiskEngine:
    def __init__(self, market_data: MarketDataProvider, config: RiskConfig | None = None) -> None:
        self.market_data = market_data
        self.config = config or RiskConfig()
        self._processed_events: set[str] = set()

    async def evaluate(
        self,
        event: NewsEvent,
        decision: AiDecision,
        *,
        market_phase: MarketPhase = MarketPhase.MARKET_HOURS,
        quantity: int = 1,
    ) -> TradeIntent:
        rule_result = evaluate_trading_signal(event, decision)
        symbol = rule_result.symbol
        if not rule_result.approved or symbol is None:
            return self._rejected(event, symbol, rule_result.reason)
        if market_phase not in self.config.allowed_market_phases:
            return self._rejected(event, symbol, f"Rejected: market phase {market_phase.value} is not allowed.")
        if event.id in self._processed_events:
            return self._rejected(event, symbol, "Rejected: duplicate event has already been evaluated for trading.")
        if quantity < 1 or quantity > self.config.max_order_quantity:
            return self._rejected(event, symbol, f"Rejected: quantity {quantity} exceeds risk limits.")

        price = await self.market_data.last_price(symbol)
        if price is None or price <= 0:
            return self._rejected(event, symbol, "Rejected: no valid market price is available.")
        notional = price * quantity
        if notional > self.config.max_order_notional:
            return self._rejected(
                event,
                symbol,
                f"Rejected: order notional {notional:.2f} exceeds {self.config.max_order_notional:.2f}.",
            )

        self._processed_events.add(event.id)
        return TradeIntent(
            event_id=event.id,
            symbol=symbol,
            side=decision.signal,
            quantity=quantity,
            entry_price=price,
            notional=notional,
            approved=True,
            reason="Approved: trading rules and risk checks passed.",
            rule_version=f"{rule_result.rule_version}+{RISK_VERSION}",
        )

    @staticmethod
    def _rejected(event: NewsEvent, symbol: str | None, reason: str) -> TradeIntent:
        return TradeIntent(
            event_id=event.id,
            symbol=symbol or "UNKNOWN",
            side=Signal.IGNORE,
            quantity=0,
            entry_price=0,
            notional=0,
            approved=False,
            reason=reason,
            rule_version=RISK_VERSION,
        )
