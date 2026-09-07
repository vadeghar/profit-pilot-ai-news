from datetime import datetime, timezone
from uuid import uuid4

from app.domain.models import PaperExecutionResult, PaperOrder, Position, Signal, TradeIntent
from app.storage import PaperTradingRepository


class PaperTradingService:
    def __init__(self, repository: PaperTradingRepository) -> None:
        self.repository = repository

    def execute(self, intent: TradeIntent) -> PaperExecutionResult:
        if not intent.approved:
            raise ValueError("Cannot execute a rejected trade intent.")
        if intent.side not in (Signal.BUY, Signal.SELL):
            raise ValueError("Only BUY and SELL trade intents can be executed.")
        if self.repository.has_order_for_event(intent.event_id):
            raise ValueError("A paper order already exists for this event.")

        existing = self.repository.get_position(intent.symbol)
        position = self._apply_fill(existing, intent)
        now = datetime.now(timezone.utc).isoformat()
        order = PaperOrder(
            id=str(uuid4()),
            event_id=intent.event_id,
            symbol=intent.symbol,
            side=intent.side,
            quantity=intent.quantity,
            fill_price=intent.entry_price,
            notional=intent.notional,
            status="FILLED",
            created_at=now,
        )
        self.repository.save_order(order)
        self.repository.save_position(position)
        return PaperExecutionResult(order=order, position=position)

    @staticmethod
    def _apply_fill(existing: Position | None, intent: TradeIntent) -> Position:
        current = existing or Position(symbol=intent.symbol, quantity=0, average_price=0, realized_pnl=0)
        signed_quantity = intent.quantity if intent.side == Signal.BUY else -intent.quantity

        if current.quantity == 0 or (current.quantity > 0 and signed_quantity > 0) or (current.quantity < 0 and signed_quantity < 0):
            new_quantity = current.quantity + signed_quantity
            total_cost = abs(current.quantity) * current.average_price + intent.quantity * intent.entry_price
            average_price = total_cost / abs(new_quantity) if new_quantity else 0
            return current.model_copy(update={"quantity": new_quantity, "average_price": average_price})

        closing_quantity = min(abs(current.quantity), intent.quantity)
        pnl_per_share = intent.entry_price - current.average_price if current.quantity > 0 else current.average_price - intent.entry_price
        realized_pnl = current.realized_pnl + closing_quantity * pnl_per_share
        new_quantity = current.quantity + signed_quantity
        if new_quantity == 0:
            average_price = 0
        elif (current.quantity > 0 and new_quantity > 0) or (current.quantity < 0 and new_quantity < 0):
            average_price = current.average_price
        else:
            average_price = intent.entry_price
        return Position(
            symbol=current.symbol,
            quantity=new_quantity,
            average_price=average_price,
            realized_pnl=realized_pnl,
        )
