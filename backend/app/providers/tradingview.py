"""TradingView WebSocket Data Feed Adapter (Adapter Pattern).

Connects to `wss://data.tradingview.com/socket.io/websocket` to stream real-time
quote ticks for active Egyptian Exchange securities and benchmark indices.

Protocol Framing Mechanics:
TradingView's quote server employs Socket.IO message framing with the format:
    `~m~<byte_length>~m~<payload>`
Multiple framed messages may arrive bundled together in a single WebSocket frame.

Heartbeat Ping/Pong:
The server periodically transmits heartbeat packets:
    `~m~<length>~m~~h~<number>` (e.g., `~m~3~m~~h~1`)
Clients must echo back the identical heartbeat frame immediately to maintain connection liveness.

Quote Data Packets:
Market updates arrive with message type 'qsd':
    `{"m": "qsd", "p": ["qs_session_id", {"n": "EGX:COMI", "s": "ok", "v": {"lp": 86.5, ...}}]}`
This module normalizes the raw payload into a uniform dictionary with price, change,
volume, high, low, and local Cairo timestamp.
"""

import asyncio
import json
import random
import re
import string
import ssl
import inspect
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
import websockets
from app.config import settings
from app.providers.base import DataProvider
from app.providers.mock_snapshot import get_initial_snapshots, generate_snapshot_quote
from app.symbols import ALL_STATIC_SYMBOLS, INDICES, normalize_ticker
from app.market_guard import check_market_hours, get_cairo_now

TV_WS_URL = "wss://data.tradingview.com/socket.io/websocket"
TV_ORIGIN = "https://www.tradingview.com"
TV_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class TradingViewWebSocketProvider(DataProvider):
    """Adapter for TradingView's live quote streaming WebSocket.

    Attributes:
        auth_token (str): TradingView user token or 'unauthorized_user_token'.
        is_connected (bool): True if upstream socket is established.
        is_paused (bool): True if streaming ingestion is paused by user.
    """

    def __init__(self):
        super().__init__(name="TradingViewWebSocketProvider")
        self.auth_token = settings.TV_AUTH_TOKEN or "unauthorized_user_token"
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running: bool = False
        self._session_id: str = self._generate_session_id("qs_")
        self._task: Optional[asyncio.Task] = None
        self._reconnect_delay = 3.0
        self._cache = get_initial_snapshots()

    def _generate_session_id(self, prefix: str = "qs_") -> str:
        """Generates random alphanumeric quote session ID required by TradingView."""
        random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
        return f"{prefix}{random_str}"

    def _format_frame(self, payload: str) -> str:
        """Encodes string into TradingView ~m~<length>~m~<payload> frame."""
        return f"~m~{len(payload)}~m~{payload}"

    def _parse_frames(self, raw_data: str) -> List[str]:
        """Splits concatenated TradingView frames into discrete payloads."""
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
            frames.append(raw_data)
        return frames

    def _to_tv_symbol(self, ticker: str) -> str:
        """Converts an internal ticker (e.g. 'COMI' or 'SHARIAH') to a TradingView symbol.

        Special case: EGX 33 Shariah index maps to 'EGX:EGX33SHR'.
        """
        clean = normalize_ticker(ticker)
        if clean == "SHARIAH":
            return "EGX:EGX33SHR"
        static_info = ALL_STATIC_SYMBOLS.get(clean)
        if static_info and "tv_symbol" in static_info:
            return static_info["tv_symbol"]
        return f"EGX:{clean}"

    def _to_internal_ticker(self, tv_sym: str) -> str:
        """Maps an incoming TradingView symbol (e.g. 'EGX:EGX33SHR') back to internal ticker."""
        clean_tv = tv_sym.upper()
        if clean_tv in ("EGX:EGX33SHR", "EGX:SHARIAH"):
            return "SHARIAH"
        for t, info in ALL_STATIC_SYMBOLS.items():
            if info.get("tv_symbol", "").upper() == clean_tv:
                return t
        if ":" in clean_tv:
            return clean_tv.split(":")[-1]
        return clean_tv

    async def start(self) -> None:
        """Starts the WebSocket connection loop in an asynchronous background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._connection_loop())
        print(f"[{self.name}] Service started.")

    async def stop(self) -> None:
        """Gracefully disconnects from TradingView and stops background workers."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        self.is_connected = False
        print(f"[{self.name}] Gracefully stopped.")

    async def pause(self) -> None:
        """Pauses real-time quote emissions without disconnecting."""
        self.is_paused = True
        print(f"[{self.name}] Stream ingestion paused by user.")

    async def resume(self) -> None:
        """Resumes real-time quote emissions."""
        self.is_paused = False
        print(f"[{self.name}] Stream ingestion resumed.")

    async def subscribe(self, symbols: List[str]) -> None:
        """Dynamically subscribes to live quotes for the specified tickers."""
        new_symbols = {normalize_ticker(s) for s in symbols} - self._subscribed_symbols
        if not new_symbols:
            return
        self._subscribed_symbols.update(new_symbols)
        if self._ws and self.is_connected:
            tv_syms = [self._to_tv_symbol(s) for s in new_symbols]
            add_msg = json.dumps({
                "m": "quote_add_symbols",
                "p": [self._session_id, *tv_syms],
            })
            try:
                await self._ws.send(self._format_frame(add_msg))
            except Exception as e:
                print(f"[{self.name}] Failed to send quote_add_symbols: {e}")

    async def unsubscribe(self, symbols: List[str]) -> None:
        """Dynamically unsubscribes from live quotes for the specified tickers."""
        remove_syms = {normalize_ticker(s) for s in symbols}.intersection(self._subscribed_symbols)
        if not remove_syms:
            return
        self._subscribed_symbols.difference_update(remove_syms)
        if self._ws and self.is_connected:
            tv_syms = [self._to_tv_symbol(s) for s in remove_syms]
            rem_msg = json.dumps({
                "m": "quote_remove_symbols",
                "p": [self._session_id, *tv_syms],
            })
            try:
                await self._ws.send(self._format_frame(rem_msg))
            except Exception as e:
                print(f"[{self.name}] Failed to send quote_remove_symbols: {e}")

    async def get_snapshot(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """Retrieves latest quote or closing snapshot for requested symbols."""
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

    async def _connection_loop(self) -> None:
        """Main connection and message ingestion loop with auto-reconnect."""
        while self._running:
            market_info = check_market_hours()
            if not market_info["is_open"]:
                print(f"[{self.name}] Market is {market_info['status']}. Serving closing snapshot.")
                await asyncio.sleep(60)
                continue

            try:
                print(f"[{self.name}] Connecting to TradingView WebSocket at {TV_WS_URL}...")
                ssl_context = ssl.create_default_context()

                # Build version-agnostic connect kwargs for websockets 13+/14+/17+
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
                    self._reconnect_delay = 3.0
                    print(f"[{self.name}] Connected to TradingView upstream WebSocket!")

                    # 1. Send authorization token
                    auth_msg = json.dumps({"m": "set_auth_token", "p": [self.auth_token]})
                    await ws.send(self._format_frame(auth_msg))

                    # 2. Establish fresh quote session
                    self._session_id = self._generate_session_id("qs_")
                    sess_msg = json.dumps({"m": "quote_create_session", "p": [self._session_id]})
                    await ws.send(self._format_frame(sess_msg))

                    # 3. Specify quote fields to stream
                    fields = [
                        "ch", "chp", "current_session", "description", "exchange",
                        "fractional", "is_tradable", "lp", "lp_time", "minmov", "minmove2",
                        "original_name", "pricescale", "pro_name", "short_name", "type",
                        "update_mode", "volume", "ask", "bid", "high_price", "low_price",
                        "open_price", "prev_close_price", "rch", "rchp",
                    ]
                    fields_msg = json.dumps({"m": "quote_set_fields", "p": [self._session_id, *fields]})
                    await ws.send(self._format_frame(fields_msg))

                    # 4. Subscribe to pinned indices + active symbols
                    all_to_sub = set(INDICES.keys()).union(self._subscribed_symbols)
                    if all_to_sub:
                        tv_symbols = [self._to_tv_symbol(s) for s in all_to_sub]
                        sub_msg = json.dumps({"m": "quote_add_symbols", "p": [self._session_id, *tv_symbols]})
                        await ws.send(self._format_frame(sub_msg))

                    # 5. Continuous message stream
                    async for raw_message in ws:
                        if not self._running:
                            break
                        await self._handle_raw_message(raw_message, ws)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[{self.name}] Connection error: {e}. Reconnecting in {self._reconnect_delay:.1f}s...")
                self.is_connected = False
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 1.5, 30.0)

        self.is_connected = False

    async def _handle_raw_message(self, raw_data: str, ws: websockets.WebSocketClientProtocol) -> None:
        """Processes framed message chunks received from TradingView."""
        frames = self._parse_frames(raw_data)
        for frame in frames:
            # Handle heartbeat ping
            if frame.startswith("~h~"):
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
                quote_obj = payload[1]
                tv_symbol = quote_obj.get("n", "")
                values = quote_obj.get("v", {})
                await self._process_quote_update(tv_symbol, values)

    async def _process_quote_update(self, tv_symbol: str, values: Dict[str, Any]) -> None:
        """Normalizes raw quote payload and emits tick."""
        ticker = self._to_internal_ticker(tv_symbol)
        existing = self._cache.get(ticker, {})

        last_price = values.get("lp", existing.get("last_price", 0.0))
        prev_close = values.get("prev_close_price", existing.get("prev_close", last_price))
        change = values.get("ch", existing.get("change", 0.0))
        change_pct = values.get("chp", existing.get("change_pct", 0.0))
        high_price = values.get("high_price", existing.get("high", last_price))
        low_price = values.get("low_price", existing.get("low", last_price))
        open_price = values.get("open_price", existing.get("open", prev_close))
        volume = values.get("volume", existing.get("volume", 0))

        if change == 0.0 and prev_close and last_price != prev_close:
            change = round(last_price - prev_close, 2)
            change_pct = round((change / prev_close) * 100, 2)

        now_cairo = get_cairo_now()

        normalized_quote = {
            "ticker": ticker,
            "tv_symbol": tv_symbol,
            "name_en": existing.get("name_en", ticker),
            "name_ar": existing.get("name_ar", ticker),
            "is_index": ticker in INDICES,
            "sector": existing.get("sector", "General"),
            "sector_ar": existing.get("sector_ar", "عام"),
            "currency": existing.get("currency", "EGP"),
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

        self._cache[ticker] = normalized_quote
        await self.emit_tick(normalized_quote)
