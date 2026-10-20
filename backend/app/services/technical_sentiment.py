"""Technical Sentiment and Quantitative Indicator Engine for EGX Securities.

Architecture & Purpose:
-----------------------
This service provides quantitative market sentiment (Bullish, Bearish, Neutral)
for Egyptian Exchange (EGX) equities, inspired by institutional terminals and
modern fintech platforms like Thndr / ThndrX.

Data Pipeline:
--------------
1. Queries TradingView's Egypt Scanner API in a single high-efficiency bulk request:
   - `Recommend.All`: TradingView's composite technical rating (-1.0 to +1.0)
     aggregating 26 technical indicators (Moving Averages, Oscillators).
   - `RSI` (14): Relative Strength Index measuring price velocity.
   - `MACD.macd` & `MACD.signal`: Moving Average Convergence Divergence trend momentum.
   - `EMA20` & `SMA50`: Short and medium-term exponential/simple moving averages.
2. Normalizes raw technical values into standardized financial signals:
   - Score > +0.15: BULLISH (Strong accumulation / upward trend)
   - Score < -0.15: BEARISH (Distribution / downward pressure)
   - Otherwise:     NEUTRAL (Consolidation / range-bound)
3. Persists technical scores to SQLite (`technical_sentiment` table) for offline/closed-market caching.
4. Provides both real-time enrichment for WebSocket quote payloads and REST endpoint lookups.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
import httpx
import pytz

from app.config import settings
from app.database import DB_PATH
from app.symbols import normalize_ticker
import aiosqlite

# TradingView Egypt Scanner Endpoint & Standard Browser Headers
TV_SCANNER_URL = "https://scanner.tradingview.com/egypt/scan"
TV_SCANNER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# In-memory sentiment cache for instant lookups during quote streaming
_sentiment_cache: Dict[str, Dict[str, Any]] = {}


async def init_sentiment_table() -> None:
    """Initializes the SQLite schema for storing quantitative technical sentiment.

    Creates `technical_sentiment` table to preserve indicator readings when the market
    is closed or when offline, ensuring fast startup without waiting for scanner responses.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS technical_sentiment (
                ticker TEXT PRIMARY KEY,
                rating_score REAL NOT NULL,
                signal TEXT NOT NULL,
                rsi REAL,
                rsi_signal TEXT,
                macd REAL,
                macd_signal REAL,
                ema20 REAL,
                sma50 REAL,
                updated_at TEXT NOT NULL
            )
        """)
        await db.commit()


def calculate_signal(score: Optional[float]) -> str:
    """Classifies a composite technical score into a standard market signal.

    Financial Rationale:
    TradingView's Recommend.All aggregates moving average crossovers and oscillators.
    - Values >= 0.15 indicate a statistically significant bullish bias.
    - Values <= -0.15 indicate a statistically significant bearish bias.
    - Between -0.15 and 0.15 represents consolidation (neutral market).

    Args:
        score: Raw float rating between -1.0 and +1.0.

    Returns:
        One of 'BULLISH', 'BEARISH', or 'NEUTRAL'.
    """
    if score is None:
        return "NEUTRAL"
    if score >= 0.15:
        return "BULLISH"
    elif score <= -0.15:
        return "BEARISH"
    return "NEUTRAL"


def calculate_rsi_signal(rsi: Optional[float]) -> str:
    """Determines momentum state from the 14-period Relative Strength Index.

    Financial Rationale:
    - RSI > 70: Overbought (Price may be extended; reversal or pause possible).
    - RSI < 30: Oversold (Heavy selling; potential technical bounce).
    - 30 to 70: Normal equilibrium range.

    Args:
        rsi: Float RSI value (0 to 100).

    Returns:
        One of 'OVERBOUGHT', 'OVERSOLD', or 'NEUTRAL'.
    """
    if rsi is None:
        return "NEUTRAL"
    if rsi >= 70.0:
        return "OVERBOUGHT"
    elif rsi <= 30.0:
        return "OVERSOLD"
    return "NEUTRAL"


async def fetch_technical_sentiment_bulk() -> Dict[str, Dict[str, Any]]:
    """Performs a non-blocking bulk scan of all EGX listed securities to compute sentiment.

    Returns:
        Dict[str, Dict[str, Any]]: Mapping of ticker symbol to technical metrics.
    """
    await init_sentiment_table()

    headers = {
        "User-Agent": TV_SCANNER_USER_AGENT,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Request comprehensive technical indicators in a single API call
    payload = {
        "filter": [{"left": "exchange", "operation": "equal", "right": "EGX"}],
        "options": {"lang": "en"},
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": [
            "name",           # 0: Ticker symbol (e.g. 'COMI')
            "close",          # 1: Last closing price
            "Recommend.All",  # 2: Composite technical rating (-1.0 to 1.0)
            "RSI",            # 3: 14-period RSI
            "MACD.macd",      # 4: MACD Line
            "MACD.signal",    # 5: MACD Signal Line
            "EMA20",          # 6: 20-period Exponential Moving Average
            "SMA50",          # 7: 50-period Simple Moving Average
        ],
        "sort": {"sortBy": "name", "sortOrder": "asc"},
        "range": [0, 500],
    }

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(TV_SCANNER_URL, json=payload, headers=headers)

        if response.status_code != 200:
            print(f"[TechnicalSentiment] Warning: Scanner returned HTTP {response.status_code}")
            return await load_cached_sentiment_from_db()

        data = response.json()
        rows = data.get("data", [])
        now_cairo = datetime.now(pytz.timezone(settings.MARKET_TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")

        results: Dict[str, Dict[str, Any]] = {}

        async with aiosqlite.connect(DB_PATH) as db:
            for item in rows:
                cols = item.get("d", [])
                if len(cols) < 3:
                    continue

                raw_ticker = cols[0]
                ticker = normalize_ticker(raw_ticker)
                close_price = cols[1]
                rec_score = cols[2] if cols[2] is not None else 0.0
                rsi_val = cols[3] if len(cols) > 3 and cols[3] is not None else None
                macd_val = cols[4] if len(cols) > 4 and cols[4] is not None else None
                macd_sig = cols[5] if len(cols) > 5 and cols[5] is not None else None
                ema20_val = cols[6] if len(cols) > 6 and cols[6] is not None else None
                sma50_val = cols[7] if len(cols) > 7 and cols[7] is not None else None

                signal = calculate_signal(rec_score)
                rsi_signal = calculate_rsi_signal(rsi_val)

                sentiment_entry = {
                    "ticker": ticker,
                    "rating_score": round(float(rec_score), 3),
                    "signal": signal,
                    "rsi": round(float(rsi_val), 1) if rsi_val is not None else None,
                    "rsi_signal": rsi_signal,
                    "macd": round(float(macd_val), 3) if macd_val is not None else None,
                    "macd_signal": round(float(macd_sig), 3) if macd_sig is not None else None,
                    "ema20": round(float(ema20_val), 2) if ema20_val is not None else None,
                    "sma50": round(float(sma50_val), 2) if sma50_val is not None else None,
                    "updated_at": now_cairo,
                }

                results[ticker] = sentiment_entry
                _sentiment_cache[ticker] = sentiment_entry

                # Persist to SQLite for offline resilience
                await db.execute("""
                    INSERT INTO technical_sentiment (
                        ticker, rating_score, signal, rsi, rsi_signal,
                        macd, macd_signal, ema20, sma50, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticker) DO UPDATE SET
                        rating_score = excluded.rating_score,
                        signal = excluded.signal,
                        rsi = excluded.rsi,
                        rsi_signal = excluded.rsi_signal,
                        macd = excluded.macd,
                        macd_signal = excluded.macd_signal,
                        ema20 = excluded.ema20,
                        sma50 = excluded.sma50,
                        updated_at = excluded.updated_at
                """, (
                    ticker,
                    sentiment_entry["rating_score"],
                    sentiment_entry["signal"],
                    sentiment_entry["rsi"],
                    sentiment_entry["rsi_signal"],
                    sentiment_entry["macd"],
                    sentiment_entry["macd_signal"],
                    sentiment_entry["ema20"],
                    sentiment_entry["sma50"],
                    sentiment_entry["updated_at"],
                ))

            await db.commit()

        print(f"[TechnicalSentiment] Successfully computed sentiment for {len(results)} EGX securities.")
        return results

    except Exception as e:
        print(f"[TechnicalSentiment] Background sync exception: {e}")
        return await load_cached_sentiment_from_db()


async def load_cached_sentiment_from_db() -> Dict[str, Dict[str, Any]]:
    """Loads previously stored sentiment data from SQLite if network is unavailable.

    Returns:
        Dict[str, Dict[str, Any]]: Cached sentiment entries keyed by ticker.
    """
    global _sentiment_cache
    try:
        await init_sentiment_table()
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM technical_sentiment") as cursor:
                rows = await cursor.fetchall()
                for r in rows:
                    d = dict(r)
                    _sentiment_cache[d["ticker"]] = d
        return _sentiment_cache
    except Exception as e:
        print(f"[TechnicalSentiment] DB load error: {e}")
        return _sentiment_cache


def get_cached_sentiment(ticker: str) -> Optional[Dict[str, Any]]:
    """Retrieves in-memory sentiment for a ticker synchronously.

    Args:
        ticker: Normalized EGX ticker symbol.

    Returns:
        Optional sentiment dictionary if present in cache.
    """
    clean = normalize_ticker(ticker)
    return _sentiment_cache.get(clean)
