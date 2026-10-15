"""
SQLite database persistence for active EGX watchlist.
Runs locally using aiosqlite.
"""

from pathlib import Path
from typing import List, Dict, Any
import aiosqlite
from symbols import DEFAULT_WATCHLIST

DB_PATH = Path(__file__).resolve().parent / "egx_watchlist.db"

async def init_db() -> None:
    """Initialize the SQLite database schema and seed default watchlist if empty."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                symbol TEXT PRIMARY KEY,
                order_index INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()

        # Check if empty, then seed defaults
        async with db.execute("SELECT COUNT(*) FROM watchlist") as cursor:
            row = await cursor.fetchone()
            count = row[0] if row else 0

        if count == 0:
            for idx, symbol in enumerate(DEFAULT_WATCHLIST):
                await db.execute(
                    "INSERT OR IGNORE INTO watchlist (symbol, order_index) VALUES (?, ?)",
                    (symbol, idx)
                )
            await db.commit()

async def get_watchlist_symbols() -> List[str]:
    """Retrieve ordered list of watchlist symbols."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT symbol FROM watchlist ORDER BY order_index ASC") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def add_symbol_to_watchlist(symbol: str) -> bool:
    """Add a symbol to the user watchlist."""
    clean_symbol = symbol.strip().upper()
    async with aiosqlite.connect(DB_PATH) as db:
        # Get current max order index
        async with db.execute("SELECT COALESCE(MAX(order_index), -1) FROM watchlist") as cursor:
            row = await cursor.fetchone()
            next_idx = (row[0] if row else -1) + 1

        try:
            await db.execute(
                "INSERT INTO watchlist (symbol, order_index) VALUES (?, ?)",
                (clean_symbol, next_idx)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False  # Already exists

async def remove_symbol_from_watchlist(symbol: str) -> bool:
    """Remove a symbol from the user watchlist."""
    clean_symbol = symbol.strip().upper()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("DELETE FROM watchlist WHERE symbol = ?", (clean_symbol,))
        await db.commit()
        return cursor.rowcount > 0
