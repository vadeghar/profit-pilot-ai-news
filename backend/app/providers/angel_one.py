from app.providers.interfaces import ExecutionProvider


class AngelOneBrokerProvider(ExecutionProvider):
    """Placeholder for the future Angel One SmartAPI adapter.

    This adapter intentionally does not connect to Angel One or place orders yet.
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
            "Angel One integration is a placeholder. Live broker execution is disabled; "
            "use PaperTradingService for execution."
        )
