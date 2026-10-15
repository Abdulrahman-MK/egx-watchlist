"""Stream Manager Service.

Coordinates upstream market WebSocket connections, client WebSocket broadcasts,
stream pausing/resuming, and clean system shutdown.
"""

import asyncio
import json
import os
import signal
import sys
from typing import Dict, Any, Set, List, Optional
from fastapi import WebSocket
from app.providers import get_data_provider
from app.providers.base import DataProvider
from app.market_guard import check_market_hours


class StreamManager:
    """Central orchestrator for market data streaming and WebSocket distribution.

    Attributes:
        provider (DataProvider): The active upstream data feed adapter.
        active_connections (Set[WebSocket]): Connected 127.0.0.1 browser clients.
        is_paused (bool): Current streaming pause state.
    """

    def __init__(self):
        self.provider: DataProvider = get_data_provider()
        self.active_connections: Set[WebSocket] = set()
        self._heartbeat_task: Optional[asyncio.Task] = None

    @property
    def is_paused(self) -> bool:
        """Returns True if upstream tick ingestion is paused."""
        return self.provider.is_paused

    async def connect_client(self, websocket: WebSocket) -> None:
        """Registers a new frontend WebSocket client."""
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect_client(self, websocket: WebSocket) -> None:
        """Unregisters a disconnected frontend WebSocket client."""
        self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Serializes and broadcasts a payload to all connected frontend clients.

        Args:
            message (Dict[str, Any]): JSON-serializable message dictionary.
        """
        if not self.active_connections:
            return
        payload = json.dumps(message)
        dead = []
        for conn in list(self.active_connections):
            try:
                await conn.send_text(payload)
            except Exception:
                dead.append(conn)
        for d in dead:
            self.disconnect_client(d)

    async def on_tick(self, quote_data: Dict[str, Any]) -> None:
        """Callback invoked by data provider whenever an individual stock quote ticks."""
        await self.broadcast({
            "type": "TICK",
            "data": quote_data,
        })

    async def start(self) -> None:
        """Starts the data provider and the market status heartbeat worker."""
        self.provider.register_callback(self.on_tick)
        await self.provider.start()
        self._heartbeat_task = asyncio.create_task(self._market_heartbeat_loop())
        print("[StreamManager] Initialized and running.")

    async def stop(self) -> None:
        """Gracefully cancels workers and halts provider."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        await self.provider.stop()
        print("[StreamManager] Stopped.")

    async def pause_stream(self) -> Dict[str, Any]:
        """Pauses upstream quote emissions and notifies all connected clients."""
        await self.provider.pause()
        await self.broadcast({
            "type": "STREAM_STATUS",
            "status": "PAUSED",
            "message": "Stream has been paused by user.",
        })
        return {"status": "PAUSED", "is_paused": True}

    async def resume_stream(self) -> Dict[str, Any]:
        """Resumes upstream quote emissions and notifies all connected clients."""
        await self.provider.resume()
        await self.broadcast({
            "type": "STREAM_STATUS",
            "status": "ACTIVE",
            "message": "Stream has resumed.",
        })
        return {"status": "ACTIVE", "is_paused": False}

    async def shutdown_system(self) -> None:
        """Executes graceful shutdown of the entire backend application.

        Actions performed:
            1. Broadcasts SYSTEM_SHUTDOWN event to all connected browser clients.
            2. Halts upstream data provider and closes active sockets.
            3. Schedules process termination via SIGTERM after brief 500ms buffer.
        """
        print("[StreamManager] Initiating clean system shutdown...")
        # 1. Notify connected UI tabs
        await self.broadcast({
            "type": "SYSTEM_SHUTDOWN",
            "message": "System has safely shut down. Database connections and market feeds closed.",
        })

        # 2. Stop provider
        await self.stop()

        # 3. Schedule asynchronous process termination
        def terminate_process():
            print("[StreamManager] Terminating process cleanly now.")
            try:
                if sys.platform == "win32":
                    # On Windows, os.kill with SIGTERM or exit
                    os._exit(0)
                else:
                    os.kill(os.getpid(), signal.SIGTERM)
            except Exception as e:
                print(f"[StreamManager] Exit error: {e}")
                os._exit(0)

        loop = asyncio.get_running_loop()
        loop.call_later(0.5, terminate_process)

    async def _market_heartbeat_loop(self) -> None:
        """Periodically broadcasts market clock & session updates every 10 seconds."""
        while True:
            try:
                m_status = check_market_hours()
                await self.broadcast({
                    "type": "MARKET_STATUS",
                    "data": m_status,
                })
            except Exception as e:
                print(f"[MarketHeartbeat] Error: {e}")
            await asyncio.sleep(10)


# Global singleton instance
stream_manager = StreamManager()
