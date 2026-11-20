"""
Application configuration using pydantic-settings.
Supports environment variables and .env configuration.
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Trading Intelligence Platform"
    API_V1_STR: str = "/api/v1"
    VERSION: str = "0.2.0"

    # Active market data provider: 'kraken' (default) or 'binance'
    DEFAULT_PROVIDER: str = Field(default="kraken", alias="DEFAULT_PROVIDER")
    MARKET_DATA_PROVIDER: Optional[str] = Field(default=None, alias="MARKET_DATA_PROVIDER")
    EXCHANGE_TIMEOUT_MS: int = 15000

    @property
    def active_provider(self) -> str:
        provider = self.MARKET_DATA_PROVIDER or self.DEFAULT_PROVIDER
        return provider.strip().lower()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
