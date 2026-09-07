import json

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Profit Pilot AI News"
    environment: str = "development"
    database_url: str = "sqlite:///backend/data/profit_pilot.db"
    redis_url: str = "redis://localhost:6379/0"
    llm_provider: str = "stub"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.7-flash"
    gemini_timeout_seconds: float = 30.0
    gemini_max_retries: int = 3
    gemini_retry_base_seconds: float = 1.0
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_timeout_seconds: float = 30.0
    market_data_provider: str = "stub"
    news_provider: str = "stub"
    news_rss_feeds: str = ""
    news_symbol_keywords_json: str = "{}"
    news_fetch_timeout_seconds: float = 10.0
    news_max_items_per_feed: int = 50
    news_poll_interval_seconds: float = 300.0
    news_trade_quantity: int = 1
    max_order_notional: float = 100_000.0
    max_order_quantity: int = 1_000

    # Angel One SmartAPI placeholders. No broker connection is made unless configured.
    angel_api_key: str | None = None
    angel_client_code: str | None = None
    angel_password: str | None = None
    angel_totp_secret: str | None = None
    angel_exchange: str = "NSE"
    angel_symbol_tokens_json: str = "{}"

    @property
    def angel_symbol_tokens(self) -> dict[str, str]:
        value = json.loads(self.angel_symbol_tokens_json)
        if not isinstance(value, dict):
            raise ValueError("ANGEL_SYMBOL_TOKENS_JSON must contain a JSON object")
        return {str(key): str(token) for key, token in value.items()}

    @property
    def news_feeds(self) -> list[str]:
        return [item.strip() for item in self.news_rss_feeds.split(",") if item.strip()]

    @property
    def news_symbol_keywords(self) -> dict[str, list[str]]:
        value = json.loads(self.news_symbol_keywords_json)
        if not isinstance(value, dict):
            raise ValueError("NEWS_SYMBOL_KEYWORDS_JSON must contain a JSON object")
        return {
            str(symbol): [str(keyword) for keyword in keywords]
            for symbol, keywords in value.items()
            if isinstance(keywords, list)
        }


settings = Settings()
