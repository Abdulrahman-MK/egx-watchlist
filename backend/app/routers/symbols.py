"""Symbols Router.

Provides endpoints for:
- Querying and searching the comprehensive EGX securities directory (`GET /api/symbols`).
- Adding custom / new IPO tickers on the fly (`POST /api/symbols/custom`).
- Manually triggering a fresh sync with TradingView's Egypt Scanner (`POST /api/symbols/sync`).
"""

from fastapi import APIRouter, Query, HTTPException, status
from pydantic import BaseModel, Field
from app.database import search_symbols_db, add_custom_ticker, get_symbol_by_ticker
from app.services.symbol_sync import sync_all_egx_symbols
from app.services.stream_manager import stream_manager
from app.symbols import normalize_ticker

router = APIRouter(prefix="/api/symbols", tags=["Symbols"])


class CustomTickerRequest(BaseModel):
    """Payload schema for adding a custom or newly listed IPO ticker."""
    ticker: str = Field(..., min_length=1, max_length=15, description="EGX ticker symbol (e.g., 'ACTF', 'COPR')")


@router.get("")
async def search_symbols(q: str = Query("", description="Search term for ticker, English name, or Arabic name")):
    """Searches the local SQLite database of ~296+ synced EGX securities."""
    results = await search_symbols_db(q)
    return {"count": len(results), "symbols": results}


@router.post("/custom")
async def add_custom_symbol(req: CustomTickerRequest):
    """Registers a custom or newly listed IPO ticker in the local database.

    Enables immediate real-time subscription for any ticker (e.g., ACTF, COPR)
    even before it appears in static dictionaries.
    """
    clean = normalize_ticker(req.ticker)
    if not clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid ticker symbol is required.",
        )

    symbol_data = await add_custom_ticker(clean)

    # Immediately subscribe on active stream
    await stream_manager.provider.subscribe([clean])

    return {
        "success": True,
        "message": f"Custom ticker {clean} registered and subscribed.",
        "symbol": symbol_data,
    }


@router.post("/sync")
async def trigger_symbol_sync():
    """Manually triggers a full synchronization scan against TradingView's Egypt Screener."""
    result = await sync_all_egx_symbols()
    return result
