"""EGX Watchlist Dashboard - FastAPI Backend Server.

Runs strictly on 127.0.0.1 with WebSockets (ws://127.0.0.1:8000/ws), SQLite persistence,
and static single-port hosting for the compiled React frontend (frontend/dist).
"""

import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import sys
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import time

from app.config import settings
from app.database import init_db, get_watchlist_symbols
from app.symbols import INDICES
from app.market_guard import check_market_hours
from app.services.symbol_sync import sync_all_egx_symbols
from app.services.stream_manager import stream_manager
from app.routers import system_router, symbols_router, watchlist_router


# Determine static frontend dist location (supports both local and PyInstaller bundled mode)
def get_frontend_dist_dir() -> Path:
    """Locates the compiled React distribution directory."""
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller bundled temporary extraction directory
        bundled_dist = Path(sys._MEIPASS) / "dist"
        if bundled_dist.exists():
            return bundled_dist

    # Local development or release structure
    local_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    return local_dist


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager: handles startup and shutdown."""
    print(f"Starting EGX Watchlist backend strictly on {settings.HOST}:{settings.PORT}...")

    # 1. Initialize SQLite database schema and seed data
    await init_db()

    # 2. Start stream manager and market heartbeat
    await stream_manager.start()

    # 3. Subscribe provider to active watchlist + 4 core indices
    active_watchlist = await get_watchlist_symbols()
    all_needed = list(set(INDICES.keys()).union(active_watchlist))
    await stream_manager.provider.subscribe(all_needed)

    # 4. Trigger background non-blocking dynamic symbol discovery from TradingView Egypt Scanner
    asyncio.create_task(sync_all_egx_symbols())

    # 5. Trigger background technical sentiment calculation and caching (Bullish/Bearish ratings)
    from app.services.technical_sentiment import fetch_technical_sentiment_bulk
    asyncio.create_task(fetch_technical_sentiment_bulk())

    yield

    # Shutdown sequence
    await stream_manager.stop()
    print("EGX Watchlist backend shut down.")


app = FastAPI(
    title="EGX Real-Time Watchlist API",
    description="Local-only, real-time Egyptian Exchange (EGX) terminal running on host " + settings.HOST,
    version="2.0.0",
    lifespan=lifespan,
)

# Request logger middleware to record access attempts from LAN / Mesh VPN
@app.middleware("http")
async def log_requests(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    start_time = time.time()
    try:
        response = await call_next(request)
        elapsed_ms = (time.time() - start_time) * 1000
        # Filter frequent local status poll to keep logs clean
        if request.url.path != "/api/status" or client_ip != "127.0.0.1":
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [HTTP] {client_ip} -> {request.method} {request.url.path} [{response.status_code}] ({elapsed_ms:.1f}ms)")
        return response
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [HTTP ERROR] {client_ip} -> {request.method} {request.url.path} : {e} ({elapsed_ms:.1f}ms)")
        raise

# CORS configuration supporting localhost and Tailscale mesh network
cors_origins = settings.cors_origins_list
allow_all = "*" in cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else cors_origins,
    allow_credentials=not allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include modular API routers
app.include_router(system_router)
app.include_router(symbols_router)
app.include_router(watchlist_router)


# Real-Time WebSocket Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Bi-directional WebSocket endpoint for streaming EGX ticks and market session state.

    Immediately transmits INITIAL_STATE upon connection, then listens for client actions.
    """
    client_host = websocket.client.host if websocket.client else "unknown"
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [WebSocket Connected] Client: {client_host}")
    await stream_manager.connect_client(websocket)
    try:
        # 1. Transmit initial market state and cached quotes
        market_info = check_market_hours()
        watchlist_syms = await get_watchlist_symbols()
        indices_syms = list(INDICES.keys())
        all_syms = list(set(indices_syms).union(watchlist_syms))

        snapshots = await stream_manager.provider.get_snapshot(all_syms)

        await websocket.send_text(json.dumps({
            "type": "INITIAL_STATE",
            "market": market_info,
            "stream_status": "PAUSED" if stream_manager.is_paused else "ACTIVE",
            "watchlist": watchlist_syms,
            "indices": {k: snapshots.get(k) for k in indices_syms if snapshots.get(k)},
            "quotes": snapshots,
        }))

        # 2. Client interaction loop
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
                action = data.get("action")
                if action == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif action == "pause":
                    await stream_manager.pause_stream()
                elif action == "resume":
                    await stream_manager.resume_stream()
                elif action == "subscribe":
                    sym = data.get("symbol")
                    if sym:
                        await stream_manager.provider.subscribe([sym.upper()])
                elif action == "unsubscribe":
                    sym = data.get("symbol")
                    if sym:
                        await stream_manager.provider.unsubscribe([sym.upper()])
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [WebSocket Disconnected] Client: {client_host}")
        stream_manager.disconnect_client(websocket)
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [WebSocket Exception] Client: {client_host} -> {e}")
        stream_manager.disconnect_client(websocket)


# Serve Static Compiled React Frontend (Single-Port Hosting)
dist_dir = get_frontend_dist_dir()
if dist_dir.exists():
    print(f"[StaticFiles] Mounting compiled React UI from: {dist_dir}")
    app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """SPA fallback: Serves index.html for any frontend client routes."""
        file_path = dist_dir / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        index_file = dist_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"error": "Frontend build files not found. Run 'npm run build' in frontend directory."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=settings.PORT,
        reload=False,
    )
