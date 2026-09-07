from __future__ import annotations

import asyncio
from typing import Any

from app.providers.interfaces import ExecutionProvider, MarketDataProvider


class AngelOneMarketDataProvider(MarketDataProvider):
    """Read-only Angel One SmartAPI adapter.

    The adapter is inert until all required credentials and a symbol-token mapping
    are supplied. It never places orders; execution remains paper-only.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client_code: str | None = None,
        password: str | None = None,
        totp_secret: str | None = None,
        symbol_tokens: dict[str, str] | None = None,
        exchange: str = "NSE",
    ) -> None:
        self.api_key = api_key
        self.client_code = client_code
        self.password = password
        self.totp_secret = totp_secret
        self.symbol_tokens = symbol_tokens or {}
        self.exchange = exchange
        self._client: Any | None = None
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return all((self.api_key, self.client_code, self.password, self.totp_secret))

    async def _ensure_session(self) -> Any:
        if not self.configured:
            raise RuntimeError("Angel One credentials are not configured.")
        if self._client is not None:
            return self._client

        async with self._lock:
            if self._client is not None:
                return self._client
            try:
                import pyotp
                from SmartApi import SmartConnect
            except ImportError as exc:
                raise RuntimeError(
                    "Angel One integration requires smartapi-python and pyotp."
                ) from exc

            client = SmartConnect(api_key=self.api_key)
            login = await asyncio.to_thread(
                client.generateSession,
                self.client_code,
                self.password,
                pyotp.TOTP(self.totp_secret).now(),
            )
            if not login or not login.get("status"):
                raise RuntimeError(f"Angel One session failed: {login}")
            self._client = client
            return client

    async def last_price(self, symbol: str) -> float | None:
        token = self.symbol_tokens.get(symbol)
        if not token:
            return None
        client = await self._ensure_session()
        response = await asyncio.to_thread(client.ltpData, self.exchange, symbol, token)
        if not response or not response.get("status"):
            raise RuntimeError(f"Angel One LTP request failed for {symbol}: {response}")
        data = response.get("data") or {}
        ltp = data.get("ltp")
        return float(ltp) if ltp is not None else None


class AngelOneBrokerProvider(ExecutionProvider):
    """Disabled broker boundary; no live Angel One orders are supported."""

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
            "Angel One order integration is disabled. Live broker execution is not supported; "
            "use PaperTradingService for paper execution."
        )
