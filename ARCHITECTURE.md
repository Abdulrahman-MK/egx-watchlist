# EGX Real-Time Watchlist & Terminal — Architecture Blueprint

This document details the architectural design, data pipelines, protocols, and failure modes of the **Egyptian Exchange (EGX) Real-Time Watchlist & Terminal**.

---

## 1. System Topology Overview

```mermaid
flowchart TD
    subgraph Upstream ["Upstream Feeds & Data Sources"]
        TV_WS["TradingView WebSocket<br/>wss://data.tradingview.com/socket.io/websocket"]
        TV_SCAN["TradingView Egypt Screener<br/>POST https://scanner.tradingview.com/egypt/scan"]
        EGX_API["EGXApi.com REST / WebSocket"]
    end

    subgraph Backend ["FastAPI Core (127.0.0.1:8000)"]
        SYNC["symbol_sync.py<br/>Discovers ~296+ EGX Equities"]
        GUARD["market_guard.py<br/>Cairo Time Evaluator (Sun-Thu 10:00-14:30)"]
        STREAM_MGR["stream_manager.py<br/>Stream Controller & WebSocket Hub"]
        ADAPTER["providers/ (Adapter Pattern)<br/>TradingView / EGXApi / MockSnapshot"]
        DB[(SQLite: egx_watchlist.db<br/>symbols & watchlist tables)]
        ROUTERS["routers/ (system, symbols, watchlist)"]
        STATIC["SPA Static Hosting<br/>Serves frontend/dist on 127.0.0.1:8000"]
    end

    subgraph Frontend ["React 19 Terminal (127.0.0.1:8000)"]
        UI_WS["useEGXWebSocket Hook<br/>ws://127.0.0.1:8000/ws"]
        CARDS["IndexCards (4 Pinned: EGX30, 70, 100, SHARIAH)"]
        TABLE["WatchlistTable (Green/Red Tick Flashing)"]
        SEARCH["StockSearchModal (Search 296+ & Custom Tickers)"]
        CTRLS["Stream Pause/Resume & Exit App Controls"]
    end

    TV_SCAN -->|On Startup & Sync| SYNC
    SYNC -->|Upsert Securities| DB
    TV_WS <-->|Framed Socket.io| ADAPTER
    EGX_API -.-> ADAPTER
    ADAPTER <--> STREAM_MGR
    STREAM_MGR <--> GUARD
    STREAM_MGR -->|Broadcast Quotes & Clock| UI_WS
    ROUTERS <--> DB
    STATIC --> Frontend
    UI_WS --> CARDS
    UI_WS --> TABLE
    SEARCH --> ROUTERS
    CTRLS --> ROUTERS
```

---

## 2. Dynamic Full-Market Discovery (`symbol_sync.py`)

Rather than relying on brittle, outdated static arrays, the terminal performs dynamic market discovery:

1. **Startup Discovery**:
   - Sends a filter query to `https://scanner.tradingview.com/egypt/scan` with `exchange = 'EGX'` and a range of `[0, 500]`.
   - Discovers all active Egyptian Exchange listings (~296+ equities across EGX 30, EGX 70, EGX 100, and recent IPOs such as `ACTF` and `COPR`).
2. **Local Caching & Enrichment**:
   - Extracted listings are merged with curated Arabic company names (`name_ar`) and sector classifications (`sector_ar`).
   - Cached into the local SQLite `symbols` table for sub-millisecond autocomplete and search filtering.
3. **On-The-Fly Custom Ticker Fallback**:
   - If an investor inputs a newly listed IPO ticker that has not yet completed screener indexing, clicking **"Add Custom EGX Ticker: [SYMBOL]"** immediately registers the symbol as `EGX:[SYMBOL]`, subscribes upstream, and begins streaming.

---

## 3. Modular Data Provider (Adapter Pattern)

All market feeds implement the abstract [`DataProvider`](file:///backend/app/providers/base.py) interface:

```mermaid
classDiagram
    class DataProvider {
        <<Abstract>>
        +str name
        +bool is_connected
        +bool is_paused
        +register_callback(cb)
        +emit_tick(quote_data)
        +start()*
        +stop()*
        +pause()*
        +resume()*
        +subscribe(symbols)*
        +unsubscribe(symbols)*
        +get_snapshot(symbols)*
    }

    class TradingViewWebSocketProvider {
        -WebSocketClientProtocol _ws
        -str _session_id
        -_format_frame(payload)
        -_parse_frames(raw_data)
        -_process_quote_update(tv_sym, values)
        +start()
        +stop()
        +pause()
        +resume()
    }

    class EGXApiProvider {
        -str api_key
        -_poll_loop()
        +start()
        +stop()
    }

    class MockSnapshotProvider {
        +generate_snapshot_quote(ticker)
        +get_initial_snapshots(symbols)
    }

    DataProvider <|-- TradingViewWebSocketProvider
    DataProvider <|-- EGXApiProvider
    DataProvider <|-- MockSnapshotProvider
```

### TradingView Framing & Heartbeat Handling
TradingView utilizes Socket.IO packet framing:
- **Packet Structure**: `~m~<byte_length>~m~<payload>`
- **Heartbeat Echo**: Incoming `~m~3~m~~h~1` frames require an identical `~m~3~m~~h~1` reply within 10 seconds to maintain session liveness.
- **Session Handshake**:
  1. `set_auth_token`: Authenticates using user token or `"unauthorized_user_token"`.
  2. `quote_create_session`: Creates a private quote session (e.g. `qs_xxxxxxxxxxxx`).
  3. `quote_set_fields`: Registers required tick properties (`lp`, `ch`, `chp`, `high_price`, `low_price`, `open_price`, `prev_close_price`, `volume`).
  4. `quote_add_symbols`: Subscribes solely to active watchlist tickers + 4 pinned indices.

### Symbol Normalization & Shariah Index Quirk
- Standard tickers map directly: `COMI` $\rightarrow$ `EGX:COMI`.
- **EGX 33 Shariah Index Quirk**: In TradingView's ticker symbology, the official Shariah index is designated as `EGX:EGX33SHR`. The adapter seamlessly maps between internal symbol `SHARIAH` and upstream `EGX:EGX33SHR`.

---

## 4. Market Hours Guard (`market_guard.py`)

The Egyptian Exchange follows Egyptian workweek conventions:
- **Trading Days**: Sunday through Thursday.
- **Weekend**: Friday and Saturday.
- **Session Timing**: 10:00 to 14:30 Africa/Cairo time (`pytz.timezone('Africa/Cairo')`).

```mermaid
stateDiagram-v2
    [*] --> EvaluatingTime
    EvaluatingTime --> WEEKEND: Day is Friday or Saturday
    EvaluatingTime --> PRE_MARKET: Sun-Thu, Time < 10:00 Cairo
    EvaluatingTime --> OPEN: Sun-Thu, 10:00 <= Time <= 14:30 Cairo
    EvaluatingTime --> CLOSED: Sun-Thu, Time > 14:30 Cairo

    OPEN --> StreamActive: Continuous Ticks Streamed
    CLOSED --> SnapshotMode: Closing Snapshot Retained (No Socket Hammering)
    WEEKEND --> SnapshotMode: Closing Snapshot Retained
    PRE_MARKET --> PreMarketMode: Countdown to 10:00 AM Open
```

---

## 5. Lifecycle, Stream Pause & Graceful Shutdown

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as React UI (Header)
    participant WS as WebSocket (/ws)
    participant SM as stream_manager.py
    participant TV as TradingView Server
    participant DB as SQLite DB

    Note over User,DB: --- User Pauses Stream ---
    User->>UI: Clicks "PAUSE"
    UI->>SM: POST /api/system/pause
    SM->>SM: Set is_paused = True
    SM->>WS: Broadcast STREAM_STATUS: PAUSED
    WS->>UI: Update Button to "PAUSED" (Pill turns Amber)

    Note over User,DB: --- User Exits Application ---
    User->>UI: Clicks "Exit App" -> Confirms
    UI->>SM: POST /api/system/shutdown
    SM->>WS: Broadcast SYSTEM_SHUTDOWN
    WS->>UI: Render Full-Screen "System Safely Shut Down" Screen
    SM->>TV: Close Upstream WebSocket Frame
    SM->>DB: Flush & Commit SQLite Connections
    SM->>SM: Terminate Process (os._exit(0))
    UI->>User: Call window.close()
```

---

## 6. Single-Port Packaging & Standalone Desktop App

### Single-Port Serving Architecture
FastAPI in `backend/main.py` serves both:
1. REST API & WebSockets on `/api/*` and `/ws`.
2. Static compiled React assets (`frontend/dist`) on `/` and `/assets/*` with SPA fallback.
This eliminates the need for separate Node/Vite runtimes in production.

### Desktop Launcher (`desktop_launcher.py`)
- Runs Uvicorn in a daemon thread bound to `127.0.0.1:8000`.
- Attempts native window creation via `pywebview`.
- Automatically falls back to Microsoft Edge / Google Chrome in App Mode:
  ```powershell
  msedge.exe --app=http://127.0.0.1:8000 --window-size=1320,860
  ```
- Automatically triggers `/api/system/shutdown` when the window is closed, cleanly freeing port 8000.
