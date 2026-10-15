import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Determine base directory (project root is one level above backend)
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

class Settings(BaseSettings):
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DATA_PROVIDER: str = "tradingview"  # "tradingview" or "egxapi"
    TV_AUTH_TOKEN: str = ""
    EGX_API_KEY: str = ""
    MARKET_TIMEZONE: str = "Africa/Cairo"
    MARKET_OPEN_HOUR: int = 10
    MARKET_OPEN_MINUTE: int = 0
    MARKET_CLOSE_HOUR: int = 14
    MARKET_CLOSE_MINUTE: int = 30
    CORS_ORIGINS: str = "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

settings = Settings()
