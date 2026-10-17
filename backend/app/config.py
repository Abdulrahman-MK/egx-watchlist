"""Application Configuration Module.

This module defines configuration settings loaded from environment variables (.env)
or default values. It adheres strictly to local-only execution constraints (127.0.0.1)
and manages settings for market hours, data providers, and CORS policies.

Typical usage example:
    from app.config import settings
    print(settings.HOST, settings.PORT)
"""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

import sys

# Determine base directory paths (supports development and PyInstaller standalone .exe)
if getattr(sys, "frozen", False):
    PROJECT_ROOT = Path(sys.executable).resolve().parent
    BACKEND_DIR = PROJECT_ROOT
    APP_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT)) / "app"
else:
    APP_DIR = Path(__file__).resolve().parent
    BACKEND_DIR = APP_DIR.parent
    PROJECT_ROOT = BACKEND_DIR.parent

# Check for .env in project root, then backend directory
ENV_FILE = PROJECT_ROOT / ".env"
if not ENV_FILE.exists():
    ENV_FILE = BACKEND_DIR / ".env"



class Settings(BaseSettings):
    """Central settings class powered by Pydantic BaseSettings.

    Attributes:
        HOST (str): Network bind address. Strictly set to 127.0.0.1 for local isolation.
        PORT (int): HTTP/WebSocket server port. Default is 8000.
        DATA_PROVIDER (str): Active market data adapter ('tradingview' or 'egxapi').
        TV_AUTH_TOKEN (str): Optional TradingView Pro/Premium user token for real-time delayless feed.
        EGX_API_KEY (str): Optional API token for egxapi.com REST/WebSocket services.
        MARKET_TIMEZONE (str): Standard timezone for the Egyptian Exchange ('Africa/Cairo').
        MARKET_OPEN_HOUR (int): Regular session open hour in Cairo (10 AM).
        MARKET_OPEN_MINUTE (int): Regular session open minute in Cairo (00).
        MARKET_CLOSE_HOUR (int): Regular session close hour in Cairo (2 PM).
        MARKET_CLOSE_MINUTE (int): Regular session close minute in Cairo (30 min -> 14:30).
        CORS_ORIGINS (str): Comma-separated list of allowed origins strictly restricted to localhost.
    """

    HOST: str = "127.0.0.1"
    PORT: int = 8000
    DATA_PROVIDER: str = "tradingview"
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
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parses comma-separated CORS_ORIGINS into a clean list of allowed URLs.

        Returns:
            List[str]: Clean list of allowed host origins.
        """
        if "*" in self.CORS_ORIGINS:
            return ["*"]
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if self.HOST == "0.0.0.0" or self.HOST.startswith("100."):
            origins.append("*")
        return list(set(origins))


settings = Settings()
