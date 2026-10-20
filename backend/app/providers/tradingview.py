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
    `{"m": "qsd", "p": ["qs_session_id", {"n": "EGX:COMI", "s": "ok", "v": {"lp": 125.0, ...}}]}`
This module normalizes the raw payload into a uniform dictionary with price, change,
volume, high, low, and local Cairo timestamp, saving ticks to SQLite for historical analysis.
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
import httpx
import websockets
from app.config import settings
from app.providers.base import DataProvider
from app.symbols import ALL_STATIC_SYMBOLS, SEED_STOCKS, INDICES, normalize_ticker
from app.market_guard import check_market_hours, get_cairo_now
from app.database import save_quote_to_db, get_cached_quotes_from_db

TV_WS_URL = "wss://data.tradingview.com/socket.io/websocket"
TV_SCANNER_URL = "https://scanner.tradingview.com/egypt/scan"
TV_ORIGIN = "https://www.tradingview.com"
TV_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class TradingViewWebSocketProvider(DataProvider):
    """Adapter for TradingView's live quote streaming WebSocket and Scanner API.

    Architectural Design:
    - Zero Mock Data: Quotes are strictly ingested from authentic TradingView endpoints.
    - Dual Ingestion Engine:
      1. Egypt Scanner API (24/7/365): Fetches real-time closing & session quotes for all 295+
         EGX equities and benchmark indices (EGX30, EGX70EWI, EGX100EWI) with full OHLCV,
         volume, and technical indicator ratings (Recommend.All, RSI).
      2. WebSocket Streaming (10:00 - 14:30 Cairo): Subscribes to live tick-by-tick market
         updates during active trading sessions, and retrieves ICE-indexed benchmarks (SHARIAH).
    - SQLite Caching: Persists authentic ticks to `latest_quotes` and `price_history`.
    """

    def __init__(self):
        super().__init__(name="TradingViewWebSocketProvider")
        self.auth_token = settings.TV_AUTH_TOKEN or "unauthorized_user_token"
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running: bool = False
        self._session_id: str = self._generate_session_id("qs_")
        self._task: Optional[asyncio.Task] = None
        self._reconnect_delay = 3.0
        # Authentic in-memory quote cache (strictly populated by real market data)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._is_syncing: bool = False

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

        Special case: EGX 33 Shariah index maps to 'EGX:SHARIAH'.
        """
        clean = normalize_ticker(ticker)
        if clean in ("SHARIAH", "EGX33SHR", "EGX33"):
            return "EGX:SHARIAH"
        static_info = ALL_STATIC_SYMBOLS.get(clean)
        if static_info and "tv_symbol" in static_info:
            return static_info["tv_symbol"]
        return f"EGX:{clean}"

    def _to_internal_ticker(self, tv_sym: str) -> str:
        """Maps an incoming TradingView symbol (e.g. 'EGX:SHARIAH') back to internal ticker."""
        clean_tv = tv_sym.upper()
        if clean_tv in ("EGX:SHARIAH", "EGX:EGX33SHR", "SHARIAH"):
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

    async def sync_authentic_market_snapshot(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """Synchronizes 100% authentic, real-time or closing market quotes from TradingView.

        Algorithmic and Financial Rationale:
        ------------------------------------
        1. TradingView's Egypt Scanner API (POST https://scanner.tradingview.com/egypt/scan)
           serves 24/7/365 without authentication. It delivers certified OHLCV, session
           highs/lows, trading volume, and composite technical momentum indicators (Recommend.All, RSI)
           for all 295+ Egyptian Exchange securities and benchmark indices (EGX30, EGX70EWI, EGX100EWI).
        2. The EGX 33 Shariah Index ('EGX:SHARIAH') is indexed separately under the ICE provider,
           requiring a dedicated one-shot WebSocket quote session handshake.
        3. This function eliminates all synthetic/mock data generation by fetching authentic numbers
           directly from the primary source and populating both memory cache and SQLite storage.

        Args:
            symbols (Optional[List[str]]): Specific tickers to update, or None to synchronize
                                           the entire Egyptian Exchange market.

        Returns:
            Dict[str, Dict[str, Any]]: Updated dictionary of normalized quotes.
        """
        headers = {
            "User-Agent": TV_USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        columns = [
            "name", "description", "close", "change", "change_abs",
            "high", "low", "open", "volume", "Recommend.All", "RSI"
        ]
        updated_quotes: Dict[str, Dict[str, Any]] = {}

        # 1. Determine query targets
        is_full_sync = symbols is None or len(symbols) == 0
        norm_symbols = [normalize_ticker(s) for s in symbols] if symbols else []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if is_full_sync:
                    # A. Bulk query all 295+ listed Egyptian equities
                    bulk_payload = {
                        "filter": [{"left": "exchange", "operation": "equal", "right": "EGX"}],
                        "columns": columns,
                        "sort": {"sortBy": "name", "sortOrder": "asc"},
                        "range": [0, 500],
                    }
                    resp_bulk = await client.post(TV_SCANNER_URL, json=bulk_payload, headers=headers)
                    if resp_bulk.status_code == 200:
                        rows = resp_bulk.json().get("data", [])
                        for r in rows:
                            tv_sym = r.get("s", "")
                            d = r.get("d", [])
                            if len(d) >= 9:
                                await self._parse_and_cache_scanner_row(tv_sym, d)

                    # B. Query core benchmark indices (categorized outside standard equity filters)
                    idx_tv_symbols = ["EGX:EGX30", "EGX:EGX70EWI", "EGX:EGX100EWI"]
                    idx_payload = {
                        "symbols": {"tickers": idx_tv_symbols},
                        "columns": columns,
                    }
                    resp_idx = await client.post(TV_SCANNER_URL, json=idx_payload, headers=headers)
                    if resp_idx.status_code == 200:
                        for r in resp_idx.json().get("data", []):
                            await self._parse_and_cache_scanner_row(r.get("s", ""), r.get("d", []))

                else:
                    # Targeted query for explicitly requested tickers
                    tv_targets = [self._to_tv_symbol(s) for s in norm_symbols if normalize_ticker(s) not in ("SHARIAH", "EGX33SHR")]
                    if tv_targets:
                        target_payload = {
                            "symbols": {"tickers": tv_targets},
                            "columns": columns,
                        }
                        resp_target = await client.post(TV_SCANNER_URL, json=target_payload, headers=headers)
                        if resp_target.status_code == 200:
                            for r in resp_target.json().get("data", []):
                                await self._parse_and_cache_scanner_row(r.get("s", ""), r.get("d", []))

        except Exception as e:
            print(f"[{self.name}] Scanner sync warning: {e}")

        # 2. Synchronize EGX 33 Shariah index if included in sync scope
        if is_full_sync or any(normalize_ticker(s) in ("SHARIAH", "EGX33SHR", "EGX33") for s in norm_symbols):
            try:
                shariah_res = await self._fetch_one_shot_closing_snapshot(["SHARIAH"])
                updated_quotes.update(shariah_res)
            except Exception as e:
                print(f"[{self.name}] Shariah index WebSocket sync warning: {e}")

        # Collect results for requested symbols or all cache
        target_keys = norm_symbols if norm_symbols else list(self._cache.keys())
        for k in target_keys:
            if k in self._cache:
                updated_quotes[k] = self._cache[k]

        return updated_quotes

    async def _parse_and_cache_scanner_row(self, tv_sym: str, d: List[Any]) -> None:
        """Parses a raw column array from TradingView Scanner and commits to memory and SQLite.

        Column Index Mapping:
            d[0]: ticker (str)
            d[1]: description / name (str)
            d[2]: close price (float)
            d[3]: change percentage (float)
            d[4]: absolute change in currency (float)
            d[5]: session high (float)
            d[6]: session low (float)
            d[7]: session open (float)
            d[8]: total volume (int)
            d[9]: Recommend.All composite technical score (-1.0 to 1.0)
            d[10]: RSI (14) Relative Strength Index
        """
        if len(d) < 9 or d[2] is None:
            return

        close_p = float(d[2])
        ch_pct = float(d[3]) if d[3] is not None else 0.0
        ch_abs = float(d[4]) if d[4] is not None else 0.0
        hi_p = float(d[5]) if d[5] is not None else close_p
        lo_p = float(d[6]) if d[6] is not None else close_p
        op_p = float(d[7]) if d[7] is not None else close_p
        vol = int(d[8]) if d[8] is not None else 0
        rec_all = float(d[9]) if (len(d) > 9 and d[9] is not None) else None
        rsi_val = float(d[10]) if (len(d) > 10 and d[10] is not None) else None
        prev_p = round(close_p - ch_abs, 2) if ch_abs is not None else close_p

        values = {
            "lp": close_p,
            "ch": ch_abs,
            "chp": ch_pct,
            "high_price": hi_p,
            "low_price": lo_p,
            "open_price": op_p,
            "volume": vol,
            "prev_close_price": prev_p,
            "recommend_all": rec_all,
            "rsi": rsi_val,
        }
        await self._process_quote_update(tv_sym, values)

    async def _fetch_scanner_closing_snapshot(self, symbols: List[str]) -> None:
        """Legacy helper redirecting to the centralized authentic market synchronizer."""
        await self.sync_authentic_market_snapshot(symbols)

    async def _fetch_one_shot_closing_snapshot(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Performs a targeted one-shot WebSocket quote session handshake.

        Used specifically for symbols requiring interactive upstream protocol negotiation
        (such as 'EGX:SHARIAH' under the ICE data feed provider).
        """
        if not symbols:
            return {}
        tv_symbols = [self._to_tv_symbol(s) for s in symbols]
        ssl_ctx = ssl.create_default_context()
        quotes_received: Dict[str, Dict[str, Any]] = {}

        try:
            sig = inspect.signature(websockets.connect)
            connect_kwargs: Dict[str, Any] = {
                "ssl": ssl_ctx,
                "ping_interval": 15,
                "ping_timeout": 15,
            }
            if "origin" in sig.parameters:
                connect_kwargs["origin"] = TV_ORIGIN
            elif "additional_headers" in sig.parameters:
                connect_kwargs["additional_headers"] = {"Origin": TV_ORIGIN, "User-Agent": TV_USER_AGENT}
            elif "extra_headers" in sig.parameters:
                connect_kwargs["extra_headers"] = {"Origin": TV_ORIGIN, "User-Agent": TV_USER_AGENT}

            async with websockets.connect(TV_WS_URL, **connect_kwargs) as ws:
                auth_msg = json.dumps({"m": "set_auth_token", "p": [self.auth_token]})
                await ws.send(self._format_frame(auth_msg))

                sess_id = self._generate_session_id("qs_snap_")
                sess_msg = json.dumps({"m": "quote_create_session", "p": [sess_id]})
                await ws.send(self._format_frame(sess_msg))

                fields = [
                    "ch", "chp", "description", "exchange", "lp", "high_price",
                    "low_price", "open_price", "prev_close_price", "volume"
                ]
                fields_msg = json.dumps({"m": "quote_set_fields", "p": [sess_id, *fields]})
                await ws.send(self._format_frame(fields_msg))

                sub_msg = json.dumps({"m": "quote_add_symbols", "p": [sess_id, *tv_symbols]})
                await ws.send(self._format_frame(sub_msg))

                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < 3.5:
                    try:
                        raw_msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    except (asyncio.TimeoutError, Exception):
                        break

                    if raw_msg.startswith("~h~"):
                        try:
                            await ws.send(self._format_frame(raw_msg))
                        except Exception:
                            pass
                        continue

                    frames = self._parse_frames(raw_msg)
                    for frame in frames:
                        try:
                            data = json.loads(frame)
                        except Exception:
                            continue
                        if data.get("m") == "qsd" and len(data.get("p", [])) >= 2:
                            quote_obj = data["p"][1]
                            tv_sym = quote_obj.get("n", "")
                            v = quote_obj.get("v", {})
                            if tv_sym and v:
                                t = self._to_internal_ticker(tv_sym)
                                await self._process_quote_update(tv_sym, v)
                                quotes_received[t] = self._cache.get(t, {})

                    if len(quotes_received) >= len(symbols):
                        break
        except Exception as e:
            print(f"[{self.name}] One-shot WebSocket handshake notice: {e}")

        return quotes_received

    async def get_snapshot(self, symbols: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
        """Retrieves verified authentic quotes or official closing snapshots for requested symbols.

        Resolution Hierarchy (Strictly Authentic):
        -------------------------------------------
        1. In-memory cache (self._cache) populated from real ticks/scans.
        2. SQLite persistent cache (latest_quotes) saved from previous sessions.
        3. Real-time synchronizer (sync_authentic_market_snapshot) to pull latest data.
        4. Zero synthetic mock prices: If offline, returns symbol metadata with last_price 0.0.
        """
        target_symbols = [normalize_ticker(s) for s in symbols] if symbols else list(self._cache.keys())
        result: Dict[str, Dict[str, Any]] = {}
        missing: List[str] = []

        # 1. In-memory cache check
        for s in target_symbols:
            if s in self._cache and self._cache[s].get("last_price", 0) > 0:
                result[s] = self._cache[s]
            else:
                missing.append(s)

        # 2. Check SQLite persistent cache
        if missing:
            try:
                db_quotes = await get_cached_quotes_from_db(missing)
                for s, q in db_quotes.items():
                    if q.get("last_price", 0) > 0:
                        self._cache[s] = q
                        result[s] = q
                        if s in missing:
                            missing.remove(s)
            except Exception as e:
                print(f"[{self.name}] DB cache lookup notice: {e}")

        # 3. Pull authentic snapshot from TradingView for any remaining missing symbols
        if missing:
            print(f"[{self.name}] Fetching authentic snapshot from TradingView for: {missing}")
            fetched = await self.sync_authentic_market_snapshot(missing)
            for s, q in fetched.items():
                if q.get("last_price", 0) > 0:
                    result[s] = q

        # 4. Fallback for completely unknown symbols (safe metadata without fake prices)
        for s in target_symbols:
            if s not in result:
                static_meta = ALL_STATIC_SYMBOLS.get(s, {})
                result[s] = {
                    "ticker": s,
                    "tv_symbol": self._to_tv_symbol(s),
                    "name_en": static_meta.get("name_en", s),
                    "name_ar": static_meta.get("name_ar", s),
                    "is_index": s in INDICES,
                    "sector": static_meta.get("sector", "General"),
                    "sector_ar": static_meta.get("sector_ar", "عام"),
                    "currency": static_meta.get("currency", "EGP"),
                    "last_price": 0.0,
                    "prev_close": 0.0,
                    "change": 0.0,
                    "change_pct": 0.0,
                    "high": 0.0,
                    "low": 0.0,
                    "open": 0.0,
                    "volume": 0,
                    "signal": "NEUTRAL",
                    "rating_score": 0.0,
                    "rsi": None,
                    "updated_at": get_cairo_now().strftime("%Y-%m-%d %H:%M:%S"),
                }

        return result

    async def _connection_loop(self) -> None:
        """Main connection and message ingestion loop with auto-reconnect."""
        # Initial synchronization: Fetch authentic quotes for all symbols and indices on startup
        try:
            print(f"[{self.name}] Initializing authentic market snapshot on startup...")
            await self.sync_authentic_market_snapshot()
            print(f"[{self.name}] Successfully cached authentic quotes for {len(self._cache)} securities.")
        except Exception as e:
            print(f"[{self.name}] Startup market snapshot notice: {e}")

        while self._running:
            market_info = check_market_hours()
            if not market_info["is_open"]:
                print(f"[{self.name}] Market is {market_info['status']}. Serving authentic closing snapshot.")
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
        """Normalizes raw quote payload, caches in SQLite, and emits tick.

        Ensures full metadata resolution (English/Arabic names, sectors) from static seeds
        when updating quotes for the first time.
        """
        ticker = self._to_internal_ticker(tv_symbol)
        existing = self._cache.get(ticker, {})
        meta = ALL_STATIC_SYMBOLS.get(ticker) or SEED_STOCKS.get(ticker) or {}

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

        # Quantitative sentiment resolution (Bullish, Bearish, Neutral)
        from app.services.technical_sentiment import get_cached_sentiment, calculate_signal
        sent = get_cached_sentiment(ticker)
        rec_score = values.get("recommend_all")
        if rec_score is None and sent:
            rec_score = sent.get("rating_score")

        if rec_score is not None:
            signal = calculate_signal(rec_score)
            rating_score = round(float(rec_score), 2)
        elif sent:
            signal = sent.get("signal", "NEUTRAL")
            rating_score = sent.get("rating_score", 0.0)
        else:
            rating_score = round(min(1.0, max(-1.0, float(change_pct) / 3.0)), 2)
            signal = calculate_signal(rating_score)

        rsi_val = values.get("rsi") or (sent.get("rsi") if sent else None)

        name_en = existing.get("name_en") or meta.get("name_en", ticker)
        name_ar = existing.get("name_ar") or meta.get("name_ar", ticker)
        sector = existing.get("sector") or meta.get("sector", "Listed Equity" if ticker not in INDICES else "Benchmark Index")
        sector_ar = existing.get("sector_ar") or meta.get("sector_ar", "أسهم مدرجة" if ticker not in INDICES else "مؤشر رئيسي")

        normalized_quote = {
            "ticker": ticker,
            "tv_symbol": tv_symbol,
            "name_en": name_en,
            "name_ar": name_ar,
            "is_index": ticker in INDICES,
            "sector": sector,
            "sector_ar": sector_ar,
            "currency": existing.get("currency") or meta.get("currency", "EGP"),
            "last_price": round(float(last_price), 2),
            "prev_close": round(float(prev_close), 2),
            "change": round(float(change), 2),
            "change_pct": round(float(change_pct), 2),
            "high": round(float(high_price), 2),
            "low": round(float(low_price), 2),
            "open": round(float(open_price), 2),
            "volume": int(volume),
            "signal": signal,
            "rating_score": rating_score,
            "rsi": rsi_val,
            "updated_at": now_cairo.strftime("%Y-%m-%d %H:%M:%S"),
        }

        self._cache[ticker] = normalized_quote

        # Persist to SQLite latest_quotes and price_history
        try:
            await save_quote_to_db(normalized_quote)
        except Exception:
            pass

        await self.emit_tick(normalized_quote)
