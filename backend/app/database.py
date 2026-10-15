"""SQLite Database Persistence for EGX Watchlist and Synced Symbol Directory.

This module manages all local data storage using asynchronous SQLite (aiosqlite):
1. `watchlist` Table: Stores the user's active, ordered watchlist.
2. `symbols` Table: Caches all ~296+ dynamically discovered EGX securities
   fetched from TradingView's Egypt Scanner, alongside custom IPO additions.

Design Principles:
- Single local file (`egx_watchlist.db`) located in the backend root.
- Asynchronous, non-blocking I/O via aiosqlite.
- Safe upsert operations to maintain custom user notes and Arabic translations.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import aiosqlite
from app.symbols import ALL_STATIC_SYMBOLS, DEFAULT_WATCHLIST, normalize_ticker

import sys

# Database file location (persists next to executable in frozen mode, or backend/ in dev)
if getattr(sys, "frozen", False):
    DB_PATH = Path(sys.executable).resolve().parent / "egx_watchlist.db"
else:
    DB_PATH = Path(__file__).resolve().parent.parent / "egx_watchlist.db"



async def init_db() -> None:
    """Initializes the SQLite schema and seeds default data if tables are empty.

    Creates:
        - `watchlist`: Stores active user watchlist tickers and ordering.
        - `symbols`: Stores the comprehensive EGX securities directory.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # 1. Watchlist table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                symbol TEXT PRIMARY KEY,
                order_index INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Comprehensive symbols directory table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS symbols (
                ticker TEXT PRIMARY KEY,
                tv_symbol TEXT NOT NULL,
                name_en TEXT NOT NULL,
                name_ar TEXT DEFAULT '',
                sector TEXT DEFAULT 'General',
                sector_ar TEXT DEFAULT 'عام',
                base_price REAL DEFAULT 0.0,
                currency TEXT DEFAULT 'EGP',
                is_index INTEGER DEFAULT 0,
                is_custom INTEGER DEFAULT 0,
                last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()

        # Seed initial watchlist if empty
        async with db.execute("SELECT COUNT(*) FROM watchlist") as cursor:
            row = await cursor.fetchone()
            count = row[0] if row else 0

        if count == 0:
            for idx, symbol in enumerate(DEFAULT_WATCHLIST):
                await db.execute(
                    "INSERT OR IGNORE INTO watchlist (symbol, order_index) VALUES (?, ?)",
                    (symbol, idx),
                )
            await db.commit()

        # Pre-populate static symbols if table is empty
        async with db.execute("SELECT COUNT(*) FROM symbols") as cursor:
            row = await cursor.fetchone()
            sym_count = row[0] if row else 0

        if sym_count == 0:
            for s_info in ALL_STATIC_SYMBOLS.values():
                await db.execute(
                    """
                    INSERT OR IGNORE INTO symbols (
                        ticker, tv_symbol, name_en, name_ar, sector, sector_ar,
                        base_price, currency, is_index, is_custom
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    (
                        s_info["ticker"],
                        s_info.get("tv_symbol", f"EGX:{s_info['ticker']}"),
                        s_info.get("name_en", s_info["ticker"]),
                        s_info.get("name_ar", s_info["ticker"]),
                        s_info.get("sector", "General"),
                        s_info.get("sector_ar", "عام"),
                        float(s_info.get("base_price", 0.0)),
                        s_info.get("currency", "EGP"),
                        1 if s_info.get("is_index") else 0,
                    ),
                )
            await db.commit()


async def upsert_symbols(symbols_list: List[Dict[str, Any]]) -> int:
    """Bulk upserts dynamically discovered securities from the TradingView Egypt Scanner.

    Preserves existing Arabic names and custom flags if already populated.

    Args:
        symbols_list (List[Dict[str, Any]]): List of stock metadata dictionaries.

    Returns:
        int: Number of symbols upserted.
    """
    if not symbols_list:
        return 0

    count = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for s in symbols_list:
            ticker = normalize_ticker(s["ticker"])
            tv_symbol = s.get("tv_symbol", f"EGX:{ticker}")
            name_en = s.get("name_en", ticker)
            name_ar = s.get("name_ar", "")
            sector = s.get("sector", "General")
            sector_ar = s.get("sector_ar", "عام")
            base_price = float(s.get("base_price", 0.0))
            currency = s.get("currency", "EGP")
            is_index = 1 if s.get("is_index") else 0
            is_custom = 1 if s.get("is_custom") else 0

            await db.execute(
                """
                INSERT INTO symbols (
                    ticker, tv_symbol, name_en, name_ar, sector, sector_ar,
                    base_price, currency, is_index, is_custom, last_synced
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(ticker) DO UPDATE SET
                    tv_symbol = excluded.tv_symbol,
                    name_en = excluded.name_en,
                    name_ar = CASE WHEN symbols.name_ar != '' THEN symbols.name_ar ELSE excluded.name_ar END,
                    sector = CASE WHEN symbols.sector != 'General' THEN symbols.sector ELSE excluded.sector END,
                    sector_ar = CASE WHEN symbols.sector_ar != 'عام' THEN symbols.sector_ar ELSE excluded.sector_ar END,
                    base_price = CASE WHEN excluded.base_price > 0 THEN excluded.base_price ELSE symbols.base_price END,
                    last_synced = CURRENT_TIMESTAMP
                """,
                (
                    ticker,
                    tv_symbol,
                    name_en,
                    name_ar,
                    sector,
                    sector_ar,
                    base_price,
                    currency,
                    is_index,
                    is_custom,
                ),
            )
            count += 1
        await db.commit()
    return count


async def get_symbol_by_ticker(ticker: str) -> Optional[Dict[str, Any]]:
    """Retrieves metadata for a specific ticker from SQLite.

    Args:
        ticker (str): Security ticker.

    Returns:
        Optional[Dict[str, Any]]: Dictionary of symbol metadata or None.
    """
    clean = normalize_ticker(ticker)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM symbols WHERE ticker = ?", (clean,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
    return None


async def search_symbols_db(query: str = "") -> List[Dict[str, Any]]:
    """Searches EGX symbols by ticker, English name, or Arabic name.

    Excludes benchmark indices from regular stock search.

    Args:
        query (str): Search string.

    Returns:
        List[Dict[str, Any]]: Matching securities ordered by ticker.
    """
    q = query.strip()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if not q:
            # Return all non-index stocks up to 350
            async with db.execute(
                "SELECT * FROM symbols WHERE is_index = 0 ORDER BY ticker ASC LIMIT 350"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
        else:
            param = f"%{q}%"
            async with db.execute(
                """
                SELECT * FROM symbols
                WHERE is_index = 0 AND (
                    ticker LIKE ? OR
                    name_en LIKE ? OR
                    name_ar LIKE ? OR
                    sector LIKE ? OR
                    sector_ar LIKE ?
                )
                ORDER BY ticker ASC
                LIMIT 100
                """,
                (param, param, param, param, param),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]


async def add_custom_ticker(ticker: str) -> Dict[str, Any]:
    """Adds a custom or newly listed IPO ticker directly to the database.

    Allows any ticker (e.g. ACTF, COPR, or any new IPO) to be subscribed to immediately.

    Args:
        ticker (str): Ticker code to add.

    Returns:
        Dict[str, Any]: Constructed or existing symbol metadata dictionary.
    """
    clean = normalize_ticker(ticker)
    existing = await get_symbol_by_ticker(clean)
    if existing:
        return existing

    tv_symbol = f"EGX:{clean}"
    name_en = f"{clean} (Custom EGX Ticker)"
    name_ar = f"{clean} (سهم مخصص)"
    sector = "Custom / Newly Listed"
    sector_ar = "مخصص / إدراج حديث"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO symbols (
                ticker, tv_symbol, name_en, name_ar, sector, sector_ar,
                base_price, currency, is_index, is_custom
            ) VALUES (?, ?, ?, ?, ?, ?, 10.0, 'EGP', 0, 1)
            """,
            (clean, tv_symbol, name_en, name_ar, sector, sector_ar),
        )
        await db.commit()

    return {
        "ticker": clean,
        "tv_symbol": tv_symbol,
        "name_en": name_en,
        "name_ar": name_ar,
        "sector": sector,
        "sector_ar": sector_ar,
        "base_price": 10.0,
        "currency": "EGP",
        "is_index": 0,
        "is_custom": 1,
    }


async def get_watchlist_symbols() -> List[str]:
    """Retrieves ordered list of user watchlist tickers from SQLite.

    Returns:
        List[str]: Active ticker codes in user-defined order.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT symbol FROM watchlist ORDER BY order_index ASC") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def add_symbol_to_watchlist(symbol: str) -> bool:
    """Adds a ticker to the active user watchlist.

    Args:
        symbol (str): Ticker symbol.

    Returns:
        bool: True if inserted, False if already present.
    """
    clean = normalize_ticker(symbol)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COALESCE(MAX(order_index), -1) FROM watchlist") as cursor:
            row = await cursor.fetchone()
            next_idx = (row[0] if row else -1) + 1

        try:
            await db.execute(
                "INSERT INTO watchlist (symbol, order_index) VALUES (?, ?)",
                (clean, next_idx),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def remove_symbol_from_watchlist(symbol: str) -> bool:
    """Removes a ticker from the active user watchlist.

    Args:
        symbol (str): Ticker symbol.

    Returns:
        bool: True if removed, False if not found.
    """
    clean = normalize_ticker(symbol)
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM watchlist WHERE symbol = ?", (clean,))
        await db.commit()
        return cursor.rowcount > 0
