from app.domain.models import PaperOrder, Signal, TradeIntent
from app.services.paper_trading import PaperTradingService
from app.storage import PaperTradingRepository, SqliteDatabase


def intent(side: Signal = Signal.BUY, quantity: int = 10, price: float = 1_500.0) -> TradeIntent:
    return TradeIntent(
        event_id="event-1",
        symbol="RELIANCE",
        side=side,
        quantity=quantity,
        entry_price=price,
        notional=quantity * price,
        approved=True,
        reason="approved",
        rule_version="trading-rules-v1+risk-engine-v1",
    )


def service() -> PaperTradingService:
    database = SqliteDatabase("sqlite:///:memory:")
    database.initialize()
    return PaperTradingService(PaperTradingRepository(database))


def test_buy_creates_position_and_filled_order() -> None:
    trading = service()
    result = trading.execute(intent())

    assert result.order.status == "FILLED"
    assert result.order.side == Signal.BUY
    assert result.position.quantity == 10
    assert result.position.average_price == 1_500.0
    assert result.position.realized_pnl == 0


def test_sell_closes_long_position_and_realizes_pnl() -> None:
    trading = service()
    trading.execute(intent(quantity=10, price=1_500.0))
    result = trading.execute(intent(side=Signal.SELL, quantity=10, price=1_550.0))

    assert result.position.quantity == 0
    assert result.position.average_price == 0
    assert result.position.realized_pnl == 500.0


def test_rejected_intent_cannot_execute() -> None:
    trading = service()
    rejected = intent()
    rejected = rejected.model_copy(update={"approved": False})

    try:
        trading.execute(rejected)
    except ValueError as exc:
        assert "rejected trade intent" in str(exc)
    else:
        raise AssertionError("Expected rejected trade intent to fail")
