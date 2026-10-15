"""Abstract Data Provider Base Class (Adapter Pattern).

This module defines the contract that all EGX data feed adapters must implement.
Adhering to the Adapter Pattern allows the application to seamlessly switch between:
- TradingView WebSocket feed (default).
- EGXApi.com REST/WebSocket services.
- Mock/Snapshot fallback mode.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Set, Callable, Awaitable, Optional


class DataProvider(ABC):
    """Abstract interface for streaming and querying EGX market quotes.

    Attributes:
        name (str): Identifier for the active provider.
        is_connected (bool): Status of the upstream socket or connection.
        is_paused (bool): Whether real-time stream ingestion is currently paused.
    """

    def __init__(self, name: str):
        self.name = name
        self.is_connected: bool = False
        self.is_paused: bool = False
        self._callbacks: List[Callable[[Dict[str, Any]], Awaitable[None]]] = []
        self._subscribed_symbols: Set[str] = set()
        self._cache: Dict[str, Dict[str, Any]] = {}

    def register_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Registers an asynchronous callback invoked whenever a quote tick arrives.

        Args:
            callback: Async callable accepting a normalized quote dictionary.
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """Unregisters an active callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    async def emit_tick(self, quote_data: Dict[str, Any]) -> None:
        """Broadcasts a tick to all registered listeners unless streaming is paused.

        Args:
            quote_data (Dict[str, Any]): Normalized quote tick dictionary.
        """
        if self.is_paused:
            return

        ticker = quote_data.get("ticker")
        if ticker:
            if ticker in self._cache:
                self._cache[ticker].update(quote_data)
            else:
                self._cache[ticker] = quote_data

        for cb in self._callbacks:
            try:
                await cb(quote_data)
            except Exception as e:
                print(f"[{self.name}] Error invoking callback: {e}")

    @abstractmethod
    async def start(self) -> None:
        """Starts upstream network connectivity and listener loops."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully closes all upstream connections and cancels background workers."""
        pass

    @abstractmethod
    async def pause(self) -> None:
        """Temporarily pauses quote ingestion without tearing down the application."""
        pass

    @abstractmethod
    async def resume(self) -> None:
        """Resumes quote ingestion."""
        pass

    @abstractmethod
    async def subscribe(self, symbols: List[str]) -> None:
        """Subscribes to live quote feeds for the specified symbols."""
        pass

    @abstractmethod
    async def unsubscribe(self, symbols: List[str]) -> None:
        """Unsubscribes from live quote feeds for the specified symbols."""
        pass

    @abstractmethod
    async def get_snapshot(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """Retrieves closing snapshots for requested or cached symbols."""
        pass
