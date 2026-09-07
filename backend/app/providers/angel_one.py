from app.providers.interfaces import ExecutionProvider, MarketDataProvider


class AngelOneMarketDataProvider(MarketDataProvider):
    """Placeholder for the future Angel One SmartAPI market-data adapter."""

    def __init__(self, *, api_key: str | None = None, client_code: str | None = None) -> None:
        self.api_key = api_key
        self.client_code = client_code

    async def last_price(self, symbol: str) -> float | None:
        raise NotImplementedError(
            "Angel One market-data integration is a placeholder. "
            "Use StubMarketDataProvider until the SmartAPI adapter is implemented."
        )


class AngelOneBrokerProvider(ExecutionProvider):
    """Placeholder for the future Angel One SmartAPI order adapter.

    This adapter intentionally does not connect to Angel One or place live orders.
    Paper trading remains the only supported execution path.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client_code: str | None = None,
        password: str | None = None,
        totp_secret: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.client_code = client_code
        self.password = password
        self.totp_secret = totp_secret

    async def place_paper_order(self, symbol: str, side: str, quantity: int) -> str:
        raise NotImplementedError(
            "Angel One order integration is a placeholder. Live broker execution is disabled; "
            "use PaperTradingService for execution."
        )
