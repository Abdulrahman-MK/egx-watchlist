"""Provider Factory Module (Adapter Pattern).

Instantiates and returns the configured DataProvider singleton based on the
DATA_PROVIDER variable defined in .env ('tradingview' or 'egxapi').
"""

from app.config import settings
from app.providers.base import DataProvider
from app.providers.tradingview import TradingViewWebSocketProvider
from app.providers.egxapi import EGXApiProvider


def get_data_provider() -> DataProvider:
    """Instantiates and returns the active market data provider adapter.

    Returns:
        DataProvider: Concrete adapter instance (TradingViewWebSocketProvider or EGXApiProvider).
    """
    provider_type = (settings.DATA_PROVIDER or "tradingview").lower().strip()
    if provider_type == "egxapi":
        return EGXApiProvider()
    elif provider_type == "tradingview":
        return TradingViewWebSocketProvider()
    else:
        print(f"Unknown DATA_PROVIDER '{provider_type}', defaulting to TradingView provider.")
        return TradingViewWebSocketProvider()
