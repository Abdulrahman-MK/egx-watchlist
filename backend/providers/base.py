"""
Abstract Base Class for EGX Data Providers (Adapter Pattern).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Set, Callable, Awaitable, Optional

class DataProvider(ABC):
    """
    Abstract interface for streaming and querying EGX market quotes.
    Subclasses implement adapters for TradingView, EGXApi, etc.
    """

    def __init__(self, name: str):
        self.name = name
        self._callbacks: List[Callable[[Dict[str, Any]], Awaitable[None]]] = []
        self._subscribed_symbols: Set[str] = set()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.is_connected: bool = False

    def register_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Register an async callback for receiving live quote tick events."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Unregister an async callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def emit_tick(self, quote_data: Dict[str, Any]) -> None:
        """Notify all registered listeners about a new or updated quote."""
        symbol = quote_data.get("ticker")
        if symbol:
            # Update internal cache
            if symbol in self._cache:
                self._cache[symbol].update(quote_data)
            else:
                self._cache[symbol] = quote_data

        for cb in self._callbacks:
            try:
                await cb(quote_data)
            except Exception as e:
                print(f"[{self.name}] Error invoking callback: {e}")

    @abstractmethod
    async def start(self) -> None:
        """Start provider network connection / streaming loop."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop and close connections."""
        pass

    @abstractmethod
    async def subscribe(self, symbols: List[str]) -> None:
        """Subscribe to live quotes for the specified symbols."""
        pass

    @abstractmethod
    async def unsubscribe(self, symbols: List[str]) -> None:
        """Unsubscribe from live quotes for the specified symbols."""
        pass

    @abstractmethod
    async def get_snapshot(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """
        Fetch a one-time closing snapshot of all or requested symbols.
        Used when market is closed or on initial client page load.
        """
        pass
