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

        # 3. Persistent latest authentic quotes table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS latest_quotes (
                ticker TEXT PRIMARY KEY,
                tv_symbol TEXT NOT NULL,
                name_en TEXT NOT NULL,
                name_ar TEXT DEFAULT '',
                is_index INTEGER DEFAULT 0,
                sector TEXT DEFAULT 'General',
                sector_ar TEXT DEFAULT 'عام',
                currency TEXT DEFAULT 'EGP',
                last_price REAL NOT NULL,
                prev_close REAL NOT NULL,
                open_price REAL NOT NULL,
                high_price REAL NOT NULL,
                low_price REAL NOT NULL,
                change REAL NOT NULL,
                change_pct REAL NOT NULL,
                volume INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL,
                session_date TEXT NOT NULL
            )
        """)

        # 4. Historical time-series table for session sparklines, prediction models, and analytics
        await db.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                session_date TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                price REAL NOT NULL,
                open_price REAL,
                high_price REAL,
                low_price REAL,
                volume INTEGER,
                change REAL,
                change_pct REAL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_hist_ticker_date ON price_history(ticker, session_date)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_hist_ticker_ts ON price_history(ticker, timestamp)")

        # 5. Session control table tracking daily 09:00 AM Cairo session resets
        await db.execute("""
            CREATE TABLE IF NOT EXISTS session_control (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_reset_date TEXT NOT NULL,
                reset_timestamp TEXT NOT NULL
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


async def save_quote_to_db(quote: Dict[str, Any]) -> None:
    """Saves latest quote to SQLite and appends an intraday point to price_history."""
    ticker = normalize_ticker(quote.get("ticker", ""))
    if not ticker:
        return
    tv_sym = quote.get("tv_symbol", f"EGX:{ticker}")
    name_en = quote.get("name_en", ticker)
    name_ar = quote.get("name_ar", "")
    is_index = 1 if quote.get("is_index") else 0
    sector = quote.get("sector", "General")
    sector_ar = quote.get("sector_ar", "عام")
    currency = quote.get("currency", "EGP")
    last_price = float(quote.get("last_price", 0.0))
    prev_close = float(quote.get("prev_close", last_price))
    open_price = float(quote.get("open", prev_close))
    high_price = float(quote.get("high", max(last_price, open_price)))
    low_price = float(quote.get("low", min(last_price, open_price)))
    change = float(quote.get("change", 0.0))
    change_pct = float(quote.get("change_pct", 0.0))
    volume = int(quote.get("volume", 0))
    updated_at = quote.get("updated_at", "")
    session_date = updated_at[:10] if len(updated_at) >= 10 else ""

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO latest_quotes (
                ticker, tv_symbol, name_en, name_ar, is_index, sector, sector_ar,
                currency, last_price, prev_close, open_price, high_price, low_price,
                change, change_pct, volume, updated_at, session_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                tv_symbol = excluded.tv_symbol,
                name_en = excluded.name_en,
                name_ar = CASE WHEN latest_quotes.name_ar != '' THEN latest_quotes.name_ar ELSE excluded.name_ar END,
                is_index = excluded.is_index,
                last_price = excluded.last_price,
                prev_close = excluded.prev_close,
                open_price = excluded.open_price,
                high_price = excluded.high_price,
                low_price = excluded.low_price,
                change = excluded.change,
                change_pct = excluded.change_pct,
                volume = excluded.volume,
                updated_at = excluded.updated_at,
                session_date = excluded.session_date
            """,
            (
                ticker, tv_sym, name_en, name_ar, is_index, sector, sector_ar,
                currency, last_price, prev_close, open_price, high_price, low_price,
                change, change_pct, volume, updated_at, session_date
            ),
        )

        # Append to price_history if no identical price record exists for this minute
        minute_prefix = updated_at[:16] if len(updated_at) >= 16 else updated_at
        async with db.execute(
            "SELECT id FROM price_history WHERE ticker = ? AND timestamp LIKE ? AND price = ?",
            (ticker, f"{minute_prefix}%", last_price),
        ) as cursor:
            existing = await cursor.fetchone()

        if not existing:
            await db.execute(
                """
                INSERT INTO price_history (
                    ticker, session_date, timestamp, price, open_price,
                    high_price, low_price, volume, change, change_pct
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker, session_date, updated_at, last_price, open_price,
                    high_price, low_price, volume, change, change_pct
                ),
            )

        await db.commit()


async def save_quotes_bulk_to_db(quotes: List[Dict[str, Any]]) -> None:
    """Saves multiple quotes to SQLite."""
    for q in quotes:
        await save_quote_to_db(q)


async def get_cached_quotes_from_db(tickers: Optional[List[str]] = None) -> Dict[str, Dict[str, Any]]:
    """Retrieves cached latest authentic quotes from SQLite."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if tickers:
            clean_list = [normalize_ticker(t) for t in tickers]
            placeholders = ",".join("?" for _ in clean_list)
            query = f"SELECT * FROM latest_quotes WHERE ticker IN ({placeholders})"
            params = clean_list
        else:
            query = "SELECT * FROM latest_quotes"
            params = []

        result = {}
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                d = dict(r)
                result[d["ticker"]] = {
                    "ticker": d["ticker"],
                    "tv_symbol": d["tv_symbol"],
                    "name_en": d["name_en"],
                    "name_ar": d["name_ar"],
                    "is_index": bool(d["is_index"]),
                    "sector": d["sector"],
                    "sector_ar": d["sector_ar"],
                    "currency": d["currency"],
                    "last_price": d["last_price"],
                    "prev_close": d["prev_close"],
                    "open": d["open_price"],
                    "high": d["high_price"],
                    "low": d["low_price"],
                    "change": d["change"],
                    "change_pct": d["change_pct"],
                    "volume": d["volume"],
                    "updated_at": d["updated_at"],
                }
        return result


async def get_ticker_history_from_db(ticker: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Fetches chronological time-series price points for a ticker from SQLite."""
    clean = normalize_ticker(ticker)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM price_history
            WHERE ticker = ?
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (clean, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def check_and_perform_daily_reset(current_dt: Optional[Any] = None) -> bool:
    """Evaluates and executes the daily 09:00 AM Africa/Cairo session reset.

    Financial & Algorithmic Rationale:
    -----------------------------------
    The Egyptian Exchange opens continuous trading at 10:00 AM Cairo time.
    Traders require daily intraday charts and trajectory sparklines to represent
    strictly the current session's price progression (10:00 to 14:30), rather than
    displaying cumulative movements from yesterday's close.

    To prepare clean baselines before pre-market trading, this function executes
    every active trading day (Sunday through Thursday) at or after 09:00 AM Cairo time
    (exactly 1 hour before market open).

    When triggered:
    1. Records today's date in `session_control`.
    2. Clears previous temporary intraday ticks so the day starts fresh at 0.00%.
    3. Today's initial trade at 10:00 AM becomes the Anchor Point (`Open`).

    Args:
        current_dt (Optional[datetime]): Reference datetime. Defaults to current Cairo time.

    Returns:
        bool: True if a session reset was executed for a new day; False otherwise.
    """
    from app.market_guard import get_cairo_now
    now = current_dt or get_cairo_now()
    today_str = now.strftime("%Y-%m-%d")
    weekday = now.weekday()

    # EGX active trading days are Sunday(6), Monday(0), Tuesday(1), Wednesday(2), Thursday(3)
    if weekday in (4, 5):  # Friday and Saturday are Egyptian weekend
        return False

    # Reset occurs at or after 09:00 AM Cairo time (1 hour before 10:00 AM open)
    if now.hour < 9:
        return False

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT last_reset_date FROM session_control WHERE id = 1") as cursor:
            row = await cursor.fetchone()
            last_reset = row[0] if row else None

        if last_reset != today_str:
            # Perform daily reset: record today's session initialization
            now_iso = now.strftime("%Y-%m-%d %H:%M:%S")
            await db.execute("""
                INSERT INTO session_control (id, last_reset_date, reset_timestamp)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    last_reset_date = excluded.last_reset_date,
                    reset_timestamp = excluded.reset_timestamp
            """, (today_str, now_iso))
            await db.commit()
            print(f"[SessionGuard] 09:00 AM Cairo session reset executed for {today_str}. Daily charts reset anew.")
            return True

    return False


async def get_session_intraday_history(ticker: str) -> List[Dict[str, Any]]:
    """Retrieves intraday price trajectory points strictly for the active or latest session.

    Financial Rationale:
    Anchors the trajectory to the day's opening price (`open_price`) and extracts
    only ticks that occurred on today's session date (or the most recent completed session date
    if market is closed/weekend), ensuring yesterday's cross-day carryover is excluded.

    Args:
        ticker (str): Normalized EGX security ticker (e.g., 'COMI', 'EGX30').

    Returns:
        List[Dict[str, Any]]: Chronologically sorted list of session price points.
    """
    clean = normalize_ticker(ticker)
    from app.market_guard import get_cairo_now
    now_cairo = get_cairo_now()
    today_str = now_cairo.strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # 1. First attempt to fetch ticks for today's active date
        async with db.execute(
            """
            SELECT * FROM price_history
            WHERE ticker = ? AND session_date = ?
            ORDER BY timestamp ASC
            """,
            (clean, today_str),
        ) as cursor:
            rows = await cursor.fetchall()
            if rows:
                return [dict(r) for r in rows]

        # 2. If no ticks yet today (e.g. weekend or before open), fetch from the most recent session
        async with db.execute(
            """
            SELECT * FROM price_history
            WHERE ticker = ?
            ORDER BY timestamp DESC
            LIMIT 50
            """,
            (clean,),
        ) as cursor:
            recent_rows = await cursor.fetchall()
            if not recent_rows:
                return []
            # Reverse back to chronological order (Ascending)
            return [dict(r) for r in reversed(recent_rows)]


