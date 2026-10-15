# EGX Real-Time Stock & Index Terminal (Egyptian Exchange)

A local-only, high-performance financial terminal and real-time watchlist for the **Egyptian Exchange (EGX)** running strictly on `127.0.0.1`.

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20WebSockets%20%7C%20SQLite-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2019%20%7C%20Vite%20%7C%20TailwindCSS-0284c7?style=for-the-badge&logo=react&logoColor=white)](https://react.dev)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Market](https://img.shields.io/badge/Market-Egyptian%20Exchange%20(EGX)-f59e0b?style=for-the-badge)](https://www.egx.com.eg)
[![License](https://img.shields.io/badge/License-MIT-slate?style=for-the-badge)](LICENSE)

---

## ⚡ Highlights

- **Dynamic Full-EGX Symbol Discovery**: Queries TradingView's Egypt Scanner on startup to discover and cache all **~296+ listed EGX securities** across EGX 30, EGX 70, EGX 100, and recent IPOs (e.g. `ACTF`, `COPR`), paired with English and Arabic company names.
- **Immediate Custom IPO Ticker Fallback**: Type any ticker in the search bar to immediately subscribe to `EGX:[INPUT]` even on its first day of listing.
- **Top Pinned Benchmark Bar**: 4 permanently pinned cards for **EGX 30**, **EGX 70 EWI**, **EGX 100 EWI**, and **EGX 33 Shariah Index** (`SHARIAH` / `EGX:EGX33SHR`).
- **Stream Controls & Clean Exit**:
  - **Pause/Resume Stream**: Pause upstream quote emissions without closing the terminal.
  - **Red Exit App Button**: Gracefully stops upstream market WebSockets, commits SQLite transactions, and terminates the backend process with a clean shutdown screen.
- **One-Click Desktop App (No Terminal Required)**: Launch silently via `Start_EGX_Tracker.bat` (native desktop window powered by `pywebview` with Edge/Chrome App Mode fallback).
- **Single-Command .EXE Packaging**: Bundle the entire app (FastAPI, SQLite, and compiled React UI) into a standalone Windows `.exe` using `python build_exe.py`.
- **Market Hours Guard (Africa/Cairo)**: Checks official EGX hours (**Sunday through Thursday, 10:00 to 14:30 Cairo time**). Outside market hours or during weekends, serves closing snapshots without hammering upstream feeds.
- **Bloomberg / TradingView Terminal Aesthetic**: Dark mode theme, JetBrains Mono font, and cell tick flashing (**green** on price up, **red** on price down).

---

## 📐 Architecture Blueprint

For an in-depth breakdown of WebSocket framing, protocol heartbeats, and sequence diagrams, refer to [**`ARCHITECTURE.md`**](file:///ARCHITECTURE.md).

```
egx-watchlist/
├── Start_EGX_Tracker.bat      # One-click silent desktop launcher
├── desktop_launcher.py        # Native desktop window runner with auto-shutdown
├── build_exe.py               # Standalone PyInstaller packaging script
├── ARCHITECTURE.md            # System blueprint, sequence diagrams, and data flow
├── README.md                  # Project documentation & setup instructions
├── .env.example               # Safe environment configuration template
├── .gitignore                 # Strict protection for credentials, DBs, and builds
├── backend/
│   ├── main.py                # FastAPI server hosting REST, WebSockets, & React SPA
│   ├── requirements.txt       # Python dependencies
│   ├── egx_watchlist.db       # Local SQLite database (auto-generated)
│   └── app/
│       ├── config.py          # Pydantic settings loading .env
│       ├── database.py        # aiosqlite persistence for symbols & watchlist
│       ├── market_guard.py    # Cairo trading week and hours evaluator
│       ├── symbols.py         # Static indices and seed company definitions
│       ├── services/
│       │   ├── symbol_sync.py # Dynamic screener sync fetching 296+ EGX equities
│       │   └── stream_manager.py # WebSocket distribution, pause/resume, and shutdown
│       ├── routers/
│       │   ├── system.py      # /api/status, /api/system/pause, /api/system/shutdown
│       │   ├── symbols.py     # /api/symbols, /api/symbols/custom, /api/symbols/sync
│       │   └── watchlist.py   # /api/watchlist, /api/snapshot
│       └── providers/
│           ├── base.py        # DataProvider abstract base class (Adapter Pattern)
│           ├── tradingview.py # TradingView WebSocket feed (Socket.IO framing)
│           ├── egxapi.py      # egxapi.com adapter
│           └── mock_snapshot.py # Realistic closing snapshot fallback
└── frontend/
    ├── index.html             # Terminal frame with JetBrains Mono font
    ├── vite.config.js         # Single-port integration settings
    ├── tailwind.config.js     # Dark terminal palette & flash animations
    └── src/
        ├── App.jsx            # Master dashboard & shutdown overlay
        ├── hooks/
        │   └── useEGXWebSocket.js # Auto-reconnecting WebSocket hook
        ├── components/
        │   ├── Header.jsx     # Terminal branding, clock, pause & exit controls
        │   ├── IndexCards.jsx # 4 pinned benchmark cards
        │   ├── WatchlistTable.jsx # Watchlist table with sorting & cell flashes
        │   ├── StockSearchModal.jsx # Instant search with custom IPO ticker addition
        │   └── MarketStatusBadge.jsx # Market session status pill
        └── utils/
            └── formatters.js  # EGP currency, volume, and percentage formatting
```

---

## 🚀 Quick Start

### Option A: One-Click Desktop Launch (Recommended)
Simply double-click **`Start_EGX_Tracker.bat`**.
- Starts the backend server silently in the background.
- Opens a dedicated, borderless application window.
- Closing the window automatically releases port 8000 and saves your data.

### Option B: Developer Mode

#### 1. Setup Environment
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

#### 2. Start Backend (Runs on 127.0.0.1:8000)
```powershell
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```
- **REST Endpoints**: `http://127.0.0.1:8000/api/status`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **WebSocket Endpoint**: `ws://127.0.0.1:8000/ws`

#### 3. Start Frontend Development Server
```powershell
cd frontend
npm install
npm run dev
```
Open **`http://127.0.0.1:5173`** in your browser.

---

## 📦 Packaging Standalone .EXE

To package the entire tracker into a single executable:

```powershell
# In project root with backend venv active:
python build_exe.py
```
This compiles the React production bundle, gathers all backend modules and hidden dependencies, and generates:
```
dist/EGX_Tracker.exe
```
You can move `EGX_Tracker.exe` anywhere on your Windows PC and launch it without installing Python or Node.js!

---

## 🔒 Security & Safe Public GitHub Guidelines

- **Protected Secrets & Databases**: `.env` and `*.db` are strictly ignored in `.gitignore`.
- **Local Isolation**: All network listeners are strictly bound to loopback `127.0.0.1`.
- **Single-Port Serving**: In production or launcher mode, FastAPI serves the compiled React assets directly, requiring only one open local port.

---

## ⚖️ Legal Disclaimer

> [!IMPORTANT]
> **Personal & Research Use Only**: This software is an open-source, local-only personal dashboard created for educational, research, and individual portfolio monitoring purposes. It connects directly from the user's local machine (`127.0.0.1`) to public quote interfaces.
> 
> This project does **not** redistribute, rebroadcast, sell, or commercialize proprietary market data from the Egyptian Exchange (EGX) or any financial institution. Users are responsible for complying with the terms of service of their chosen upstream data providers.
