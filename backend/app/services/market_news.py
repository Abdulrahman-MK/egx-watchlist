"""Daily Scraped Market News and Catalyst Sentiment Service for EGX Securities.

Architecture & Purpose:
-----------------------
This service provides actionable intelligence for Egyptian Exchange securities by
scraping, parsing, and classifying real-time news headlines from established financial
news aggregators (Google News, Egyptian financial press, Mubasher, and Enterprise Press).

Catalyst Sentiment Engine:
--------------------------
Traders require clarity on whether recent headlines represent buying catalysts (pulling the stock UP)
or distribution risks (pushing the stock DOWN). Each headline is evaluated through a bilingual
financial keyword lexicon (English and Arabic):

1. BULLISH Catalysts (Upward Pressure):
   - Strong quarterly earnings, dividend declarations, credit rating upgrades,
     cross-border acquisitions, production capacity expansions, or strategic joint ventures.
2. BEARISH Catalysts (Downward Pressure):
   - Net losses, revenue contraction, regulatory fines, litigation, credit downgrades,
     debt restructuring distress, or key executive departures.
3. NEUTRAL / Informational:
   - Ordinary General Assembly notices, administrative filings, and macro market context.

Performance & Resilience:
-------------------------
- In-memory caching with a 10-minute TTL avoids redundant network queries during modal navigation.
- Graceful fallbacks ensure continuous operation even during upstream feed latency.
"""

import asyncio
from datetime import datetime
import re
import time
from typing import Dict, Any, List, Optional
import urllib.parse
import xml.etree.ElementTree as ET
import httpx

from app.symbols import ALL_STATIC_SYMBOLS, SEED_STOCKS, INDICES, normalize_ticker

# In-memory news cache: { "TICKER": (expires_at, payload) }
_news_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
NEWS_CACHE_TTL = 600.0  # 10 minutes cache per ticker

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Bilingual Financial Catalyst Dictionaries
BULLISH_KEYWORDS = [
    # English keywords
    "profit", "surge", "gain", "record", "growth", "dividend", "expansion",
    "jump", "soar", "upgrade", "contract", "acquisition", "rebound", "revenue up",
    "outperform", "buy", "rally", "approval", "digital bank", "positive", "partner",
    # Arabic keywords
    "أرباح", "ارتفاع", "نمو", "توزيع أرباح", "زيادة", "صفقة", "قفزة", "صعود",
    "استحواذ", "توسع", "إيجابي", "مكاسب", "شراكة", "موافقة", "إيرادات"
]

BEARISH_KEYWORDS = [
    # English keywords
    "loss", "drop", "fall", "slump", "decline", "penalty", "fine", "lawsuit",
    "investigation", "debt", "downgrade", "plunge", "selloff", "inflation pressure",
    "deficit", "negative", "warns", "delay", "freeze", "crash",
    # Arabic keywords
    "خسائر", "تراجع", "هبوط", "غرامة", "انخفاض", "تحقيق", "ديون", "ضغوط",
    "نزول", "سلبي", "انهيار", "تأجيل", "تجميد", "دعوى"
]


def classify_headline_catalyst(title: str) -> tuple[str, str]:
    """Evaluates headline text to classify catalyst bias and explain potential price impact.

    Args:
        title: Headline string.

    Returns:
        tuple[str, str]: (catalyst_signal, impact_explanation)
            - catalyst_signal: 'BULLISH', 'BEARISH', or 'NEUTRAL'
            - impact_explanation: Concise description of directional pressure.
    """
    clean_title = title.lower()
    bullish_count = sum(1 for kw in BULLISH_KEYWORDS if kw in clean_title)
    bearish_count = sum(1 for kw in BEARISH_KEYWORDS if kw in clean_title)

    if bullish_count > bearish_count:
        return (
            "BULLISH",
            "Positive corporate catalyst reported (e.g., earnings growth, expansion, or strategic approval), exerting potential upward buying pressure."
        )
    elif bearish_count > bullish_count:
        return (
            "BEARISH",
            "Negative corporate headwind reported (e.g., contraction, regulatory scrutiny, or market pressure), exerting potential downward selling pressure."
        )
    else:
        return (
            "NEUTRAL",
            "Standard market coverage or regulatory disclosure with neutral directional impact."
        )


async def get_symbol_news(ticker: str) -> Dict[str, Any]:
    """Scrapes and analyzes latest news headlines for a specific security or index.

    Queries both English and Arabic feeds from trusted sources via Google News RSS,
    merging and sorting articles chronologically.

    Args:
        ticker: Security ticker (e.g., 'COMI', 'EGX30').

    Returns:
        Dict containing ticker, overall catalyst consensus, and list of news articles.
    """
    clean_ticker = normalize_ticker(ticker)
    now_time = time.time()

    # Check cache first
    if clean_ticker in _news_cache:
        expires_at, cached_data = _news_cache[clean_ticker]
        if now_time < expires_at:
            return cached_data

    meta = ALL_STATIC_SYMBOLS.get(clean_ticker) or SEED_STOCKS.get(clean_ticker) or {}
    name_en = meta.get("name_en", clean_ticker)
    name_ar = meta.get("name_ar", clean_ticker)

    # Clean company name to optimize search specificity
    clean_name = re.sub(r"\b(S\.A\.E|S\.A\.E\.|SAE|EGYPT|SOCIETE|ANONYME)\b", "", name_en, flags=re.IGNORECASE).strip()
    if not clean_name:
        clean_name = clean_ticker

    # Build targeted search queries
    if clean_ticker in INDICES:
        query_en = f"{clean_ticker} Egypt stock exchange index"
        query_ar = f"مؤشر {clean_ticker} البورصة المصرية"
    else:
        query_en = f'"{clean_name}" Egypt OR (EGX {clean_ticker})'
        query_ar = f'"{name_ar}" البورصة المصرية OR {clean_ticker}'

    articles: List[Dict[str, Any]] = []
    seen_titles = set()

    async with httpx.AsyncClient(timeout=8.0) as client:
        # A. Query English financial feed
        try:
            url_en = f"https://news.google.com/rss/search?q={urllib.parse.quote(query_en)}&hl=en-US&gl=US&ceid=US:en"
            resp_en = await client.get(url_en, headers={"User-Agent": USER_AGENT})
            if resp_en.status_code == 200:
                root = ET.fromstring(resp_en.text)
                for item in root.findall(".//item")[:8]:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_elem = item.find("pubDate")
                    src_elem = item.find("source")

                    if title_elem is not None and title_elem.text:
                        raw_title = title_elem.text
                        # Normalize title key to eliminate cross-source duplicates
                        norm_key = re.sub(r"[^\w\s]", "", raw_title.lower())[:40]
                        if norm_key in seen_titles:
                            continue
                        seen_titles.add(norm_key)

                        catalyst, explanation = classify_headline_catalyst(raw_title)
                        source_name = src_elem.text if (src_elem is not None and src_elem.text) else "Financial News"

                        articles.append({
                            "title": raw_title,
                            "link": link_elem.text if link_elem is not None else "",
                            "published_at": pub_elem.text if pub_elem is not None else "",
                            "source": source_name,
                            "catalyst": catalyst,
                            "impact": explanation,
                            "language": "en"
                        })
        except Exception as e:
            print(f"[MarketNews] English news fetch notice for {clean_ticker}: {e}")

        # B. Query Arabic financial feed
        try:
            url_ar = f"https://news.google.com/rss/search?q={urllib.parse.quote(query_ar)}&hl=ar&gl=EG&ceid=EG:ar"
            resp_ar = await client.get(url_ar, headers={"User-Agent": USER_AGENT})
            if resp_ar.status_code == 200:
                root_ar = ET.fromstring(resp_ar.text)
                for item in root_ar.findall(".//item")[:6]:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_elem = item.find("pubDate")
                    src_elem = item.find("source")

                    if title_elem is not None and title_elem.text:
                        raw_title = title_elem.text
                        norm_key = re.sub(r"[^\w\s]", "", raw_title)[:40]
                        if norm_key in seen_titles:
                            continue
                        seen_titles.add(norm_key)

                        catalyst, explanation = classify_headline_catalyst(raw_title)
                        source_name = src_elem.text if (src_elem is not None and src_elem.text) else "صحافة المال والأعمال"

                        articles.append({
                            "title": raw_title,
                            "link": link_elem.text if link_elem is not None else "",
                            "published_at": pub_elem.text if pub_elem is not None else "",
                            "source": source_name,
                            "catalyst": catalyst,
                            "impact": explanation,
                            "language": "ar"
                        })
        except Exception as e:
            print(f"[MarketNews] Arabic news fetch notice for {clean_ticker}: {e}")

    # Fallback to general EGX market news if security-specific coverage is scarce
    if len(articles) < 2:
        try:
            url_gen = "https://news.google.com/rss/search?q=Egyptian+Exchange+EGX30+stocks&hl=en-US&gl=US&ceid=US:en"
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp_gen = await client.get(url_gen, headers={"User-Agent": USER_AGENT})
                if resp_gen.status_code == 200:
                    root_gen = ET.fromstring(resp_gen.text)
                    for item in root_gen.findall(".//item")[:4]:
                        title_elem = item.find("title")
                        link_elem = item.find("link")
                        pub_elem = item.find("pubDate")
                        src_elem = item.find("source")
                        if title_elem is not None and title_elem.text:
                            raw_title = title_elem.text
                            norm_key = re.sub(r"[^\w\s]", "", raw_title.lower())[:40]
                            if norm_key not in seen_titles:
                                seen_titles.add(norm_key)
                                catalyst, explanation = classify_headline_catalyst(raw_title)
                                articles.append({
                                    "title": raw_title,
                                    "link": link_elem.text if link_elem is not None else "",
                                    "published_at": pub_elem.text if pub_elem is not None else "",
                                    "source": src_elem.text if (src_elem is not None and src_elem.text) else "Market General",
                                    "catalyst": catalyst,
                                    "impact": explanation,
                                    "language": "en"
                                })
        except Exception:
            pass

    # Consensus Catalyst Calculation
    bullish_articles = sum(1 for a in articles if a["catalyst"] == "BULLISH")
    bearish_articles = sum(1 for a in articles if a["catalyst"] == "BEARISH")

    if bullish_articles > bearish_articles:
        overall_catalyst = "BULLISH_CATALYST"
        overall_summary = f"News sentiment exhibits positive upward momentum with {bullish_articles} bullish headlines signaling supportive fundamentals or buying catalysts."
    elif bearish_articles > bullish_articles:
        overall_catalyst = "BEARISH_CATALYST"
        overall_summary = f"News sentiment exhibits cautious downward pressure with {bearish_articles} bearish headlines signaling risk exposure or market headwinds."
    else:
        overall_catalyst = "NEUTRAL"
        overall_summary = "News coverage exhibits balanced or range-bound sentiment with no dominant directional bias."

    payload = {
        "ticker": clean_ticker,
        "name_en": name_en,
        "name_ar": name_ar,
        "overall_catalyst": overall_catalyst,
        "overall_summary": overall_summary,
        "total_articles": len(articles),
        "articles": articles[:10],
    }

    # Store in memory cache
    _news_cache[clean_ticker] = (now_time + NEWS_CACHE_TTL, payload)
    return payload
