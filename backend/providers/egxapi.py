"""
EGXApi Provider (Adapter Pattern).
Connects to egxapi.com REST / WebSocket service using EGX_API_KEY from .env.
Falls back smoothly to cached closing snapshots when API key is unconfigured or rate limited.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
import httpx
from config import settings
from providers.base import DataProvider
from providers.mock_snapshot import get_initial_snapshots
from symbols import ALL_SYMBOLS, INDICES, get_symbol_info
from market_guard import check_market_hours, get_cairo_now

EGX_API_BASE_URL = "https://api.egxapi.com/v1"

class EGXApiProvider(DataProvider):
    """
    Adapter connecting to egxapi.com using EGX_API_KEY.
    Fetches real-time market data during trading hours.
    """

    def __init__(self):
        super().__init__(name="EGXApiProvider")
        self.api_key = settings.EGX_API_KEY
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._cache = get_initial_snapshots()
        self._poll_interval = 3.0  # seconds

    async def start(self) -> None:
        """Start the polling / stream worker."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        print(f"[{self.name}] Started EGXApi provider (API Key configured: {bool(self.api_key)}).")

    async def stop(self) -> None:
        """Stop provider worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        self.is_connected = False
        print(f"[{self.name}] Stopped.")

    async def subscribe(self, symbols: List[str]) -> None:
        """Add symbols to subscribed set."""
        self._subscribed_symbols.update(symbols)

    async def unsubscribe(self, symbols: List[str]) -> None:
        """Remove symbols from subscribed set."""
        self._subscribed_symbols.difference_update(symbols)

    async def get_snapshot(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """Return cached or snapshot quotes."""
        target_symbols = symbols if symbols else list(self._cache.keys())
        result = {}
        for s in target_symbols:
            if s in self._cache:
                result[s] = self._cache[s]
            else:
                snap = get_initial_snapshots([s]).get(s)
                if snap:
                    self._cache[s] = snap
                    result[s] = snap
        return result

    async def _poll_loop(self) -> None:
        """Polling loop for egxapi.com."""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key

        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            while self._running:
                market_info = check_market_hours()
                if not market_info["is_open"]:
                    # Outside market hours, sleep 60s
                    self.is_connected = True
                    await asyncio.sleep(60)
                    continue

                if not self.api_key:
                    # No API key provided; run in graceful standby/snapshot mode
                    self.is_connected = True
                    await asyncio.sleep(self._poll_interval)
                    continue

                try:
                    symbols_to_fetch = list(set(INDICES.keys()).union(self._subscribed_symbols))
                    if not symbols_to_fetch:
                        await asyncio.sleep(self._poll_interval)
                        continue

                    # Attempt request to egxapi.com
                    resp = await client.get(
                        f"{EGX_API_BASE_URL}/quotes",
                        params={"symbols": ",".join(symbols_to_fetch)}
                    )
                    if resp.status_code == 200:
                        self.is_connected = True
                        data = resp.json()
                        quotes_list = data if isinstance(data, list) else data.get("quotes", [])
                        for item in quotes_list:
                            ticker = item.get("symbol", "").upper().replace("EGX:", "")
                            info = get_symbol_info(ticker) or {}
                            now_cairo = get_cairo_now()
                            norm = {
                                "ticker": ticker,
                                "tv_symbol": info.get("tv_symbol", f"EGX:{ticker}"),
                                "name_en": info.get("name_en", ticker),
                                "name_ar": info.get("name_ar", ticker),
                                "is_index": info.get("is_index", False),
                                "sector": info.get("sector", ""),
                                "sector_ar": info.get("sector_ar", ""),
                                "currency": info.get("currency", "EGP"),
                                "last_price": float(item.get("price", item.get("last", 0.0))),
                                "prev_close": float(item.get("prev_close", 0.0)),
                                "change": float(item.get("change", 0.0)),
                                "change_pct": float(item.get("change_percent", 0.0)),
                                "high": float(item.get("high", 0.0)),
                                "low": float(item.get("low", 0.0)),
                                "open": float(item.get("open", 0.0)),
                                "volume": int(item.get("volume", 0)),
                                "updated_at": now_cairo.strftime("%Y-%m-%d %H:%M:%S"),
                            }
                            self._cache[ticker] = norm
                            await self.emit_tick(norm)
                    else:
                        print(f"[{self.name}] egxapi.com returned status {resp.status_code}")
                except Exception as e:
                    print(f"[{self.name}] Polling error: {e}")
                    self.is_connected = False

                await asyncio.sleep(self._poll_interval)
