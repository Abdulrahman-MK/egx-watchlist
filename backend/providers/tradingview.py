"""
TradingView WebSocket Data Provider (Adapter Pattern).
Connects to wss://data.tradingview.com/socket.io/websocket to stream
live quote ticks for active EGX symbols and indices.
"""

import asyncio
import json
import random
import re
import string
import ssl
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
import websockets
from config import settings
from providers.base import DataProvider
from providers.mock_snapshot import get_initial_snapshots
from symbols import ALL_SYMBOLS, INDICES, get_symbol_info
from market_guard import check_market_hours, get_cairo_now

TV_WS_URL = "wss://data.tradingview.com/socket.io/websocket"
TV_ORIGIN = "https://www.tradingview.com"
TV_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

class TradingViewWebSocketProvider(DataProvider):
    """
    Adapter connecting to TradingView's quote streaming WebSocket.
    Translates raw socket.io framing and quote packets into normalized ticks.
    """

    def __init__(self):
        super().__init__(name="TradingViewWebSocketProvider")
        self.auth_token = settings.TV_AUTH_TOKEN or "unauthorized_user_token"
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running: bool = False
        self._session_id: str = self._generate_session_id("qs_")
        self._task: Optional[asyncio.Task] = None
        self._reconnect_delay = 3
        # Prepopulate cache with standard snapshots
        self._cache = get_initial_snapshots()

    def _generate_session_id(self, prefix: str = "qs_") -> str:
        random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
        return f"{prefix}{random_str}"

    def _format_frame(self, payload: str) -> str:
        """Format string into TradingView ~m~<length>~m~<payload> frame."""
        return f"~m~{len(payload)}~m~{payload}"

    def _parse_frames(self, raw_data: str) -> List[str]:
        """Split bundled TradingView frames into individual payloads."""
        frames = []
        pattern = re.compile(r"~m~(\d+)~m~")
        pos = 0
        while pos < len(raw_data):
            match = pattern.match(raw_data, pos)
            if not match:
                break
            length = int(match.group(1))
            start_payload = match.end()
            end_payload = start_payload + length
            payload = raw_data[start_payload:end_payload]
            frames.append(payload)
            pos = end_payload
        if not frames and raw_data:
            # Fallback if no delimiter pattern matched
            frames.append(raw_data)
        return frames

    def _to_tv_symbol(self, ticker: str) -> str:
        """Map internal ticker or index to TradingView symbol."""
        info = get_symbol_info(ticker)
        if info and "tv_symbol" in info:
            return info["tv_symbol"]
        return f"EGX:{ticker.upper()}"

    def _to_internal_ticker(self, tv_sym: str) -> str:
        """Map TradingView symbol back to internal ticker."""
        clean_tv = tv_sym.upper()
        for t, info in ALL_SYMBOLS.items():
            if info.get("tv_symbol", "").upper() == clean_tv:
                return t
        # Strip exchange prefix (e.g. EGX:COMI -> COMI)
        if ":" in clean_tv:
            return clean_tv.split(":")[-1]
        return clean_tv

    async def start(self) -> None:
        """Start the WebSocket connection and message loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._connection_loop())
        print(f"[{self.name}] Started TradingView provider.")

    async def stop(self) -> None:
        """Stop the provider gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        if self._ws:
            await self._ws.close()
            self._ws = None
        self.is_connected = False
        print(f"[{self.name}] Stopped.")

    async def subscribe(self, symbols: List[str]) -> None:
        """Add symbols to live subscription set."""
        new_symbols = set(symbols) - self._subscribed_symbols
        if not new_symbols:
            return
        self._subscribed_symbols.update(new_symbols)
        if self._ws and self.is_connected:
            tv_syms = [self._to_tv_symbol(s) for s in new_symbols]
            add_msg = json.dumps({
                "m": "quote_add_symbols",
                "p": [self._session_id, *tv_syms]
            })
            try:
                await self._ws.send(self._format_frame(add_msg))
            except Exception as e:
                print(f"[{self.name}] Failed to send quote_add_symbols: {e}")

    async def unsubscribe(self, symbols: List[str]) -> None:
        """Remove symbols from live subscription set."""
        remove_syms = set(symbols).intersection(self._subscribed_symbols)
        if not remove_syms:
            return
        self._subscribed_symbols.difference_update(remove_syms)
        if self._ws and self.is_connected:
            tv_syms = [self._to_tv_symbol(s) for s in remove_syms]
            rem_msg = json.dumps({
                "m": "quote_remove_symbols",
                "p": [self._session_id, *tv_syms]
            })
            try:
                await self._ws.send(self._format_frame(rem_msg))
            except Exception as e:
                print(f"[{self.name}] Failed to send quote_remove_symbols: {e}")

    async def get_snapshot(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """Return the latest cached quotes or closing snapshot."""
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

    async def _connection_loop(self) -> None:
        """Continuous reconnection loop with market hours check."""
        headers = {
            "Origin": TV_ORIGIN,
            "User-Agent": TV_USER_AGENT,
        }

        while self._running:
            # Check market hours: if market is closed, sleep longer and avoid hammering external socket
            market_info = check_market_hours()
            if not market_info["is_open"]:
                # Outside market hours, refresh closing snapshot once every 60s
                print(f"[{self.name}] Market is {market_info['status']}. Retaining closing snapshot.")
                await asyncio.sleep(60)
                continue

            try:
                print(f"[{self.name}] Connecting to TradingView WebSocket at {TV_WS_URL}...")
                ssl_context = ssl.create_default_context()

                # Build connect kwargs dynamically based on installed websockets version
                import inspect
                sig = inspect.signature(websockets.connect)
                connect_kwargs: Dict[str, Any] = {
                    "ssl": ssl_context,
                    "ping_interval": 20,
                    "ping_timeout": 20,
                }
                if "origin" in sig.parameters:
                    connect_kwargs["origin"] = TV_ORIGIN
                if "user_agent_header" in sig.parameters:
                    connect_kwargs["user_agent_header"] = TV_USER_AGENT
                elif "additional_headers" in sig.parameters:
                    connect_kwargs["additional_headers"] = {
                        "Origin": TV_ORIGIN,
                        "User-Agent": TV_USER_AGENT,
                    }
                elif "extra_headers" in sig.parameters:
                    connect_kwargs["extra_headers"] = {
                        "Origin": TV_ORIGIN,
                        "User-Agent": TV_USER_AGENT,
                    }

                async with websockets.connect(TV_WS_URL, **connect_kwargs) as ws:
                    self._ws = ws
                    self.is_connected = True
                    self._reconnect_delay = 3
                    print(f"[{self.name}] Connected to TradingView!")

                    # 1. Send auth token
                    auth_msg = json.dumps({"m": "set_auth_token", "p": [self.auth_token]})
                    await ws.send(self._format_frame(auth_msg))

                    # 2. Create quote session
                    self._session_id = self._generate_session_id("qs_")
                    sess_msg = json.dumps({"m": "quote_create_session", "p": [self._session_id]})
                    await ws.send(self._format_frame(sess_msg))

                    # 3. Set desired quote fields
                    fields = [
                        "ch", "chp", "current_session", "description", "exchange",
                        "fractional", "is_tradable", "lp", "lp_time", "minmov", "minmove2",
                        "original_name", "pricescale", "pro_name", "short_name", "type",
                        "update_mode", "volume", "ask", "bid", "high_price", "low_price",
                        "open_price", "prev_close_price", "rch", "rchp"
                    ]
                    fields_msg = json.dumps({"m": "quote_set_fields", "p": [self._session_id, *fields]})
                    await ws.send(self._format_frame(fields_msg))

                    # 4. Subscribe to pinned indices + active symbols
                    all_to_sub = set(INDICES.keys()).union(self._subscribed_symbols)
                    if all_to_sub:
                        tv_symbols = [self._to_tv_symbol(s) for s in all_to_sub]
                        sub_msg = json.dumps({"m": "quote_add_symbols", "p": [self._session_id, *tv_symbols]})
                        await ws.send(self._format_frame(sub_msg))

                    # 5. Listen for incoming ticks & heartbeats
                    async for raw_message in ws:
                        if not self._running:
                            break
                        await self._handle_raw_message(raw_message, ws)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.name}] WebSocket connection error: {e}. Reconnecting in {self._reconnect_delay}s...")
                self.is_connected = False
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 1.5, 30)

        self.is_connected = False

    async def _handle_raw_message(self, raw_data: str, ws: websockets.WebSocketClientProtocol) -> None:
        """Handle incoming socket.io framed packet from TradingView."""
        frames = self._parse_frames(raw_data)
        for frame in frames:
            # Handle heartbeat: ~h~<number>
            if frame.startswith("~h~"):
                # Reply heartbeat
                try:
                    await ws.send(self._format_frame(frame))
                except Exception:
                    pass
                continue

            try:
                data = json.loads(frame)
            except Exception:
                continue

            msg_type = data.get("m")
            payload = data.get("p", [])

            if msg_type == "qsd" and len(payload) >= 2:
                # Quote data packet: p = [session_id, {"n": "EGX:COMI", "s": "ok", "v": {...}}]
                quote_obj = payload[1]
                tv_symbol = quote_obj.get("n", "")
                values = quote_obj.get("v", {})
                await self._process_quote_update(tv_symbol, values)

    async def _process_quote_update(self, tv_symbol: str, values: Dict[str, Any]) -> None:
        """Convert TradingView values dict into normalized quote dict and broadcast."""
        ticker = self._to_internal_ticker(tv_symbol)
        info = get_symbol_info(ticker) or {}

        # Fetch existing cached entry to merge
        existing = self._cache.get(ticker, {})

        last_price = values.get("lp", existing.get("last_price", info.get("base_price", 0.0)))
        prev_close = values.get("prev_close_price", existing.get("prev_close", last_price))
        change = values.get("ch", existing.get("change", 0.0))
        change_pct = values.get("chp", existing.get("change_pct", 0.0))
        high_price = values.get("high_price", existing.get("high", last_price))
        low_price = values.get("low_price", existing.get("low", last_price))
        open_price = values.get("open_price", existing.get("open", prev_close))
        volume = values.get("volume", existing.get("volume", 0))

        # In case change was not provided directly but price moved
        if change == 0.0 and prev_close and last_price != prev_close:
            change = round(last_price - prev_close, 2)
            change_pct = round((change / prev_close) * 100, 2)

        now_cairo = get_cairo_now()

        normalized_quote = {
            "ticker": ticker,
            "tv_symbol": tv_symbol,
            "name_en": info.get("name_en", ticker),
            "name_ar": info.get("name_ar", ticker),
            "is_index": info.get("is_index", False),
            "sector": info.get("sector", ""),
            "sector_ar": info.get("sector_ar", ""),
            "currency": info.get("currency", "EGP"),
            "last_price": round(float(last_price), 2),
            "prev_close": round(float(prev_close), 2),
            "change": round(float(change), 2),
            "change_pct": round(float(change_pct), 2),
            "high": round(float(high_price), 2),
            "low": round(float(low_price), 2),
            "open": round(float(open_price), 2),
            "volume": int(volume),
            "updated_at": now_cairo.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Update cache and emit
        self._cache[ticker] = normalized_quote
        await self.emit_tick(normalized_quote)
