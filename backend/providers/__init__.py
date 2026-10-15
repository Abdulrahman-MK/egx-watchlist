"""
Provider package factory.
Instantiates the selected DataProvider according to DATA_PROVIDER in .env.
"""

from config import settings
from providers.base import DataProvider
from providers.tradingview import TradingViewWebSocketProvider
from providers.egxapi import EGXApiProvider

def get_data_provider() -> DataProvider:
    """Instantiate and return the configured data provider."""
    provider_type = (settings.DATA_PROVIDER or "tradingview").lower().strip()
    if provider_type == "egxapi":
        return EGXApiProvider()
    elif provider_type == "tradingview":
        return TradingViewWebSocketProvider()
    else:
        print(f"Unknown DATA_PROVIDER '{provider_type}', falling back to TradingView provider.")
        return TradingViewWebSocketProvider()
