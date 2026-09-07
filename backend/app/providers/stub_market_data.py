from app.providers.interfaces import MarketDataProvider


class StubMarketDataProvider(MarketDataProvider):
    def __init__(self, prices: dict[str, float] | None = None) -> None:
        self.prices = prices or {
            "RELIANCE": 1_500.0,
            "TCS": 3_800.0,
        }

    async def last_price(self, symbol: str) -> float | None:
        return self.prices.get(symbol)
