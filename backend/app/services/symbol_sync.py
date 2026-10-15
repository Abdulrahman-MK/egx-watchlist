"""Dynamic EGX Securities Discovery Service via TradingView Egypt Scanner.

This service queries TradingView's official Egypt Screener API on startup and
periodically to dynamically discover all ~290+ listed EGX companies (e.g., ACTF, COPR,
and recent IPOs), ensuring zero missing stocks and full coverage beyond static lists.

API Endpoint:
    POST https://scanner.tradingview.com/egypt/scan

Data Flow:
    1. Send filter query with exchange='EGX' and columns for name, description, close, etc.
    2. Parse response data rows.
    3. Cross-reference with curated Arabic and sector dictionaries.
    4. Upsert into local SQLite `symbols` table for lightning-fast search in the UI.
"""

import asyncio
from typing import Dict, Any, List, Optional
import httpx
from app.database import upsert_symbols
from app.symbols import SEED_STOCKS, normalize_ticker

TV_SCANNER_URL = "https://scanner.tradingview.com/egypt/scan"
TV_SCANNER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


async def sync_all_egx_symbols() -> Dict[str, Any]:
    """Queries TradingView's Egypt Scanner to discover and cache all active EGX stocks.

    Returns:
        Dict[str, Any]: Summary dictionary containing:
            - success (bool): True if sync succeeded.
            - count (int): Number of securities discovered and stored.
            - error (Optional[str]): Error message if request failed.
    """
    headers = {
        "User-Agent": TV_SCANNER_USER_AGENT,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "filter": [{"left": "exchange", "operation": "equal", "right": "EGX"}],
        "options": {"lang": "en"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": [
            "name",
            "description",
            "close",
            "change",
            "volume",
            "currency",
        ],
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 500],
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(TV_SCANNER_URL, json=payload, headers=headers)

        if response.status_code != 200:
            err_msg = f"Scanner returned HTTP {response.status_code}: {response.text[:120]}"
            print(f"[SymbolSync] Warning: {err_msg}")
            return {"success": False, "count": 0, "error": err_msg}

        data = response.json()
        rows = data.get("data", [])
        total_discovered = len(rows)

        parsed_symbols: List[Dict[str, Any]] = []
        for item in rows:
            tv_sym = item.get("s", "")  # e.g., 'EGX:ACTF'
            cols = item.get("d", [])
            if not tv_sym or not cols:
                continue

            ticker = normalize_ticker(cols[0] if len(cols) > 0 else tv_sym)
            name_en = cols[1] if len(cols) > 1 and cols[1] else ticker
            close_price = float(cols[2]) if len(cols) > 2 and cols[2] is not None else 0.0
            currency = cols[5] if len(cols) > 5 and cols[5] else "EGP"

            # Check if we have curated Arabic translation and sector in SEED_STOCKS
            seed_info = SEED_STOCKS.get(ticker, {})
            name_ar = seed_info.get("name_ar", "")
            sector = seed_info.get("sector", "Listed Equity")
            sector_ar = seed_info.get("sector_ar", "أسهم مدرجة")

            parsed_symbols.append({
                "ticker": ticker,
                "tv_symbol": tv_sym,
                "name_en": name_en,
                "name_ar": name_ar,
                "sector": sector,
                "sector_ar": sector_ar,
                "base_price": close_price,
                "currency": currency,
                "is_index": 0,
                "is_custom": 0,
            })

        upserted_count = await upsert_symbols(parsed_symbols)
        print(f"[SymbolSync] Successfully discovered and cached {upserted_count} EGX securities in SQLite.")
        return {
            "success": True,
            "count": upserted_count,
            "total_remote": total_discovered,
            "error": None,
        }

    except Exception as e:
        err_msg = f"Symbol sync exception: {str(e)}"
        print(f"[SymbolSync] Error: {err_msg}. Using local fallback symbols.")
        return {"success": False, "count": 0, "error": err_msg}
