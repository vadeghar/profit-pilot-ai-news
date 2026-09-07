from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Profit Pilot AI News"
    environment: str = "development"
    database_url: str = "sqlite:///backend/data/profit_pilot.db"
    redis_url: str = "redis://localhost:6379/0"
    llm_provider: str = "stub"
    max_order_notional: float = 100_000.0
    max_order_quantity: int = 1_000

    # Angel One SmartAPI placeholders. No broker connection is made yet.
    angel_api_key: str | None = None
    angel_client_code: str | None = None
    angel_password: str | None = None
    angel_totp_secret: str | None = None


settings = Settings()
