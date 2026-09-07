from app.domain.models import PositionSnapshot
from app.providers.interfaces import MarketDataProvider
from app.storage import PaperTradingRepository


class PortfolioService:
    def __init__(self, repository: PaperTradingRepository, market_data: MarketDataProvider) -> None:
        self.repository = repository
        self.market_data = market_data

    async def snapshots(self) -> list[PositionSnapshot]:
        snapshots: list[PositionSnapshot] = []
        for position in self.repository.list_positions():
            current_price = await self.market_data.last_price(position.symbol)
            if current_price is None or current_price <= 0:
                current_price = position.average_price
            unrealized_pnl = position.quantity * (current_price - position.average_price)
            snapshots.append(
                PositionSnapshot(
                    **position.model_dump(),
                    current_price=current_price,
                    unrealized_pnl=unrealized_pnl,
                    total_pnl=position.realized_pnl + unrealized_pnl,
                )
            )
        return snapshots
