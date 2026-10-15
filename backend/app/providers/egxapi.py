"""EGXApi.com Data Feed Adapter (Adapter Pattern).

Connects to `egxapi.com` REST/WebSocket services using `EGX_API_KEY` from .env.
Falls back smoothly to cached closing snapshots when API key is unconfigured or rate-limited.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
import httpx
from app.config import settings
from app.providers.base import DataProvider
from app.providers.mock_snapshot import get_initial_snapshots, generate_snapshot_quote
from app.symbols import ALL_STATIC_SYMBOLS, INDICES, normalize_ticker
from app.market_guard import check_market_hours, get_cairo_now

EGX_API_BASE_URL = "https://api.egxapi.com/v1"


class EGXApiProvider(DataProvider):
    """Adapter for egxapi.com market quotes API."""

    def __init__(self):
        super().__init__(name="EGXApiProvider")
        self.api_key = settings.EGX_API_KEY
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._cache = get_initial_snapshots()
        self._poll_interval = 3.0

    async def start(self) -> None:
        """Starts the polling worker task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        print(f"[{self.name}] Service started (API Key present: {bool(self.api_key)}).")

    async def stop(self) -> None:
        """Stops the polling worker task."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        self.is_connected = False
        print(f"[{self.name}] Gracefully stopped.")

    async def pause(self) -> None:
        """Pauses polling ingestion."""
        self.is_paused = True
        print(f"[{self.name}] Paused.")

    async def resume(self) -> None:
        """Resumes polling ingestion."""
        self.is_paused = False
        print(f"[{self.name}] Resumed.")

    async def subscribe(self, symbols: List[str]) -> None:
        """Adds symbols to poll set."""
        self._subscribed_symbols.update(normalize_ticker(s) for s in symbols)

    async def unsubscribe(self, symbols: List[str]) -> None:
        """Removes symbols from poll set."""
        self._subscribed_symbols.difference_update(normalize_ticker(s) for s in symbols)

    async def get_snapshot(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """Returns cached or snapshot quotes."""
        target_symbols = [normalize_ticker(s) for s in symbols] if symbols else list(self._cache.keys())
        result = {}
        for s in target_symbols:
            if s in self._cache:
                result[s] = self._cache[s]
            else:
                snap = generate_snapshot_quote(s)
                self._cache[s] = snap
                result[s] = snap
        return result

    async def _poll_loop(self) -> None:
        """Periodic query loop against egxapi.com."""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key

        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            while self._running:
                market_info = check_market_hours()
                if not market_info["is_open"]:
                    self.is_connected = True
                    await asyncio.sleep(60)
                    continue

                if not self.api_key or self.is_paused:
                    self.is_connected = True
                    await asyncio.sleep(self._poll_interval)
                    continue

                try:
                    symbols_to_fetch = list(set(INDICES.keys()).union(self._subscribed_symbols))
                    if not symbols_to_fetch:
                        await asyncio.sleep(self._poll_interval)
                        continue

                    resp = await client.get(
                        f"{EGX_API_BASE_URL}/quotes",
                        params={"symbols": ",".join(symbols_to_fetch)},
                    )
                    if resp.status_code == 200:
                        self.is_connected = True
                        data = resp.json()
                        quotes_list = data if isinstance(data, list) else data.get("quotes", [])
                        for item in quotes_list:
                            ticker = normalize_ticker(item.get("symbol", ""))
                            existing = self._cache.get(ticker, {})
                            now_cairo = get_cairo_now()
                            norm = {
                                "ticker": ticker,
                                "tv_symbol": f"EGX:{ticker}",
                                "name_en": existing.get("name_en", ticker),
                                "name_ar": existing.get("name_ar", ticker),
                                "is_index": ticker in INDICES,
                                "sector": existing.get("sector", "General"),
                                "sector_ar": existing.get("sector_ar", "عام"),
                                "currency": "EGP",
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
                        print(f"[{self.name}] API returned status {resp.status_code}")
                except Exception as e:
                    print(f"[{self.name}] Polling exception: {e}")
                    self.is_connected = False

                await asyncio.sleep(self._poll_interval)
