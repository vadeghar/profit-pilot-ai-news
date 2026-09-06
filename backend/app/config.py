from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Profit Pilot AI News"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://profitpilot:profitpilot@localhost:5432/profitpilot"
    redis_url: str = "redis://localhost:6379/0"
    llm_provider: str = "stub"


settings = Settings()
