from pathlib import Path

import pytest

from app.domain.models import Position
from app.providers.stub_market_data import StubMarketDataProvider
from app.services.portfolio import PortfolioService
from app.storage import PaperTradingRepository, SqliteDatabase


@pytest.mark.asyncio
async def test_portfolio_reports_unrealized_and_total_pnl(tmp_path: Path) -> None:
    database = SqliteDatabase(f"sqlite:///{tmp_path / 'portfolio.db'}")
    database.initialize()
    repository = PaperTradingRepository(database)
    repository.save_position(Position(symbol="RELIANCE", quantity=10, average_price=1_400.0, realized_pnl=250.0))

    service = PortfolioService(repository, StubMarketDataProvider())
    snapshots = await service.snapshots()

    assert len(snapshots) == 1
    assert snapshots[0].current_price == 1_500.0
    assert snapshots[0].unrealized_pnl == 1_000.0
    assert snapshots[0].total_pnl == 1_250.0
