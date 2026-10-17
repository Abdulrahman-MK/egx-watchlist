"""Watchlist and Market Snapshot Router.

Provides endpoints for:
- Retrieving saved user watchlist with rich corporate metadata (`GET /api/watchlist`).
- Adding a ticker to the active watchlist and subscribing (`POST /api/watchlist`).
- Removing a ticker from the active watchlist and unsubscribing (`DELETE /api/watchlist/{symbol}`).
- Fetching full snapshot of the 4 core indices + watchlist items (`GET /api/snapshot`).
"""

from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.database import (
    get_watchlist_symbols,
    add_symbol_to_watchlist,
    remove_symbol_from_watchlist,
    get_symbol_by_ticker,
    add_custom_ticker,
)
from app.symbols import INDICES, normalize_ticker
from app.market_guard import check_market_hours
from app.services.stream_manager import stream_manager

router = APIRouter(prefix="/api", tags=["Watchlist"])


class WatchlistAddRequest(BaseModel):
    """Schema for adding a ticker to user watchlist."""
    symbol: str = Field(..., min_length=1, max_length=20, description="EGX Ticker Symbol (e.g. 'COMI', 'ACTF')")


@router.get("/watchlist")
async def get_watchlist():
    """Retrieves the user's active watchlist symbols populated with database metadata."""
    symbols = await get_watchlist_symbols()
    detailed: List[Dict[str, Any]] = []

    for sym in symbols:
        info = await get_symbol_by_ticker(sym)
        if info:
            detailed.append(info)
        else:
            detailed.append({
                "ticker": sym,
                "tv_symbol": f"EGX:{sym}",
                "name_en": sym,
                "name_ar": sym,
                "sector": "General",
                "sector_ar": "عام",
                "is_index": 0,
            })

    return {"watchlist": symbols, "details": detailed}


@router.post("/watchlist")
async def add_to_watchlist(req: WatchlistAddRequest):
    """Adds a ticker to the user watchlist and dynamically registers it with the data provider."""
    sym = normalize_ticker(req.symbol)
    if not sym:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid symbol specified.",
        )

    # Ensure symbol exists in symbols table or register as custom
    info = await get_symbol_by_ticker(sym)
    if not info:
        info = await add_custom_ticker(sym)

    added = await add_symbol_to_watchlist(sym)
    if not added:
        return {"success": False, "message": f"{sym} is already in your watchlist.", "symbol": sym}

    # Subscribe on active stream
    await stream_manager.provider.subscribe([sym])

    # Fetch initial quote to broadcast immediately
    snap = await stream_manager.provider.get_snapshot([sym])
    quote_data = snap.get(sym)

    updated_list = await get_watchlist_symbols()
    await stream_manager.broadcast({
        "type": "WATCHLIST_UPDATED",
        "watchlist": updated_list,
        "new_quote": quote_data,
    })

    return {"success": True, "message": f"Added {sym} to watchlist.", "symbol": sym}


@router.delete("/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str):
    """Removes a ticker from the user watchlist and unsubscribes it from upstream feeds."""
    sym = normalize_ticker(symbol)
    removed = await remove_symbol_from_watchlist(sym)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symbol '{sym}' not found in your watchlist.",
        )

    await stream_manager.provider.unsubscribe([sym])

    updated_list = await get_watchlist_symbols()
    await stream_manager.broadcast({
        "type": "WATCHLIST_UPDATED",
        "watchlist": updated_list,
        "removed_symbol": sym,
    })

    return {"success": True, "message": f"Removed {sym} from watchlist.", "symbol": sym}


@router.get("/snapshot")
async def get_snapshot():
    """Retrieves the unified closing/current snapshot for benchmark indices and watchlist."""
    market_info = check_market_hours()
    watchlist_syms = await get_watchlist_symbols()
    indices_syms = list(INDICES.keys())
    all_syms = list(set(indices_syms).union(watchlist_syms))

    snapshots = await stream_manager.provider.get_snapshot(all_syms)

    indices_data = {k: snapshots.get(k) for k in indices_syms if snapshots.get(k)}
    watchlist_data = [snapshots.get(k) for k in watchlist_syms if snapshots.get(k)]

    return {
        "market": market_info,
        "indices": indices_data,
        "watchlist": watchlist_data,
        "raw": snapshots,
    }


@router.get("/history/{symbol}")
async def get_history(symbol: str, limit: int = 100):
    """Retrieves chronological price history data points for sparklines and ML prediction modeling."""
    from app.database import get_ticker_history_from_db
    sym = normalize_ticker(symbol)
    rows = await get_ticker_history_from_db(sym, limit=limit)
    return {
        "ticker": sym,
        "count": len(rows),
        "history": rows,
    }

