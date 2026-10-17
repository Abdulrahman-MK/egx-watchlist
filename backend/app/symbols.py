"""EGX Benchmark Indices and Seed Symbols Dictionary.

This module houses definitions for:
- 4 Core Pinned Indices: EGX30, EGX70EWI, EGX100EWI, and SHARIAH (EGX 33 Shariah).
- High-liquidity seed stocks with verified English and Arabic names and sectors.
- Default watchlist presets for initial database bootstrap.

EGX Market Quirks Handled:
- TradingView symbol for EGX 33 Shariah Index is 'EGX:SHARIAH'.
- Dual English and Arabic corporate nomenclatures are maintained for high-clarity search.
"""

from typing import Dict, Any, List, Optional

# Core Benchmark Indices permanently pinned at the top of the terminal
INDICES: Dict[str, Dict[str, Any]] = {
    "EGX30": {
        "ticker": "EGX30",
        "tv_symbol": "EGX:EGX30",
        "name_en": "EGX 30 Index",
        "name_ar": "مؤشر إيجي إكس 30",
        "is_index": True,
        "base_price": 52273.30,
        "currency": "EGP",
        "sector": "Benchmark Index",
        "sector_ar": "المؤشر الرئيسي",
    },
    "EGX70EWI": {
        "ticker": "EGX70EWI",
        "tv_symbol": "EGX:EGX70EWI",
        "name_en": "EGX 70 EWI",
        "name_ar": "مؤشر إيجي إكس 70 متساوي الأوزان",
        "is_index": True,
        "base_price": 18481.50,
        "currency": "EGP",
        "sector": "Small & Mid Cap Index",
        "sector_ar": "مؤشر الشركات المتوسطة والصغيرة",
    },
    "EGX100EWI": {
        "ticker": "EGX100EWI",
        "tv_symbol": "EGX:EGX100EWI",
        "name_en": "EGX 100 EWI",
        "name_ar": "مؤشر إيجي إكس 100 متساوي الأوزان",
        "is_index": True,
        "base_price": 24607.40,
        "currency": "EGP",
        "sector": "Broad Market Index",
        "sector_ar": "المؤشر الأوسع نطاقاً",
    },
    "SHARIAH": {
        "ticker": "SHARIAH",
        "tv_symbol": "EGX:SHARIAH",
        "name_en": "EGX 33 Shariah Index",
        "name_ar": "مؤشر الشريعة إيجي إكس 33",
        "is_index": True,
        "base_price": 6378.90,
        "currency": "EGP",
        "sector": "Shariah Compliant Index",
        "sector_ar": "مؤشر الشريعة الإسلامية",
    },
}

# Seed stocks dictionary for initial cache, sector definitions, and Arabic names
SEED_STOCKS: Dict[str, Dict[str, Any]] = {
    "COMI": {
        "ticker": "COMI",
        "tv_symbol": "EGX:COMI",
        "name_en": "Commercial International Bank (CIB)",
        "name_ar": "البنك التجاري الدولي - مصر",
        "sector": "Banking & Financial Services",
        "sector_ar": "بنوك وخدمات مالية",
        "base_price": 86.50,
        "currency": "EGP",
    },
    "TMGH": {
        "ticker": "TMGH",
        "tv_symbol": "EGX:TMGH",
        "name_en": "Talaat Moustafa Group Holding",
        "name_ar": "مجموعة طلعت مصطفى القابضة",
        "sector": "Real Estate",
        "sector_ar": "عقارات",
        "base_price": 62.40,
        "currency": "EGP",
    },
    "ETEL": {
        "ticker": "ETEL",
        "tv_symbol": "EGX:ETEL",
        "name_en": "Telecom Egypt (WE)",
        "name_ar": "المصرية للاتصالات",
        "sector": "Telecommunications",
        "sector_ar": "اتصالات",
        "base_price": 38.25,
        "currency": "EGP",
    },
    "FWRY": {
        "ticker": "FWRY",
        "tv_symbol": "EGX:FWRY",
        "name_en": "Fawry Banking & Payment",
        "name_ar": "فوري لتكنولوجيا البنوك والمدفوعات الإلكترونية",
        "sector": "Non-Bank Financial Services",
        "sector_ar": "خدمات مالية غير مصرفية",
        "base_price": 7.95,
        "currency": "EGP",
    },
    "SWDY": {
        "ticker": "SWDY",
        "tv_symbol": "EGX:SWDY",
        "name_en": "Elsewedy Electric",
        "name_ar": "السويدي إليكتريك",
        "sector": "Industrial Goods & Services",
        "sector_ar": "سلع وخدمات صناعية",
        "base_price": 54.10,
        "currency": "EGP",
    },
    "HRHO": {
        "ticker": "HRHO",
        "tv_symbol": "EGX:HRHO",
        "name_en": "EFG Holding (Hermes)",
        "name_ar": "إي إف جي القابضة (هيرميس)",
        "sector": "Investment Banking & Finance",
        "sector_ar": "خدمات مالية غير مصرفية",
        "base_price": 22.80,
        "currency": "EGP",
    },
    "ABUK": {
        "ticker": "ABUK",
        "tv_symbol": "EGX:ABUK",
        "name_en": "Abu Qir Fertilizers",
        "name_ar": "أبو قير للأسمدة والصناعات الكيماوية",
        "sector": "Basic Resources & Chemicals",
        "sector_ar": "موارد أساسية وكيماويات",
        "base_price": 64.75,
        "currency": "EGP",
    },
    "MOPCO": {
        "ticker": "MOPCO",
        "tv_symbol": "EGX:MFPC",
        "name_en": "Misr Fertilizers Production (MOPCO)",
        "name_ar": "مصر لإنتاج الأسمدة - موبكو",
        "sector": "Basic Resources & Chemicals",
        "sector_ar": "موارد أساسية وكيماويات",
        "base_price": 48.90,
        "currency": "EGP",
    },
    "AMOC": {
        "ticker": "AMOC",
        "tv_symbol": "EGX:AMOC",
        "name_en": "Alexandria Mineral Oils (AMOC)",
        "name_ar": "الإسكندرية للزيوت المعدنية - أموك",
        "sector": "Energy & Support Services",
        "sector_ar": "طاقة وخدمات مساندة",
        "base_price": 10.35,
        "currency": "EGP",
    },
    "ORAS": {
        "ticker": "ORAS",
        "tv_symbol": "EGX:ORAS",
        "name_en": "Orascom Construction PLC",
        "name_ar": "أوراسكوم كونستراكشون بي إل سي",
        "sector": "Construction & Materials",
        "sector_ar": "تشييد ومواد بناء",
        "base_price": 275.00,
        "currency": "EGP",
    },
    "EFID": {
        "ticker": "EFID",
        "tv_symbol": "EGX:EFID",
        "name_en": "Edita Food Industries",
        "name_ar": "إيديتا للصناعات الغذائية",
        "sector": "Food, Beverage & Tobacco",
        "sector_ar": "أغذية ومشروبات",
        "base_price": 32.50,
        "currency": "EGP",
    },
    "ADIB": {
        "ticker": "ADIB",
        "tv_symbol": "EGX:ADIB",
        "name_en": "Abu Dhabi Islamic Bank - Egypt",
        "name_ar": "مصرف أبو ظبي الإسلامي - مصر",
        "sector": "Banking & Financial Services",
        "sector_ar": "بنوك وخدمات مالية",
        "base_price": 45.60,
        "currency": "EGP",
    },
    "ACTF": {
        "ticker": "ACTF",
        "tv_symbol": "EGX:ACTF",
        "name_en": "Act Financial for Financial Consulting",
        "name_ar": "أكت فاينانشال للاستشارات المالية",
        "sector": "Financial Services",
        "sector_ar": "خدمات مالية",
        "base_price": 3.80,
        "currency": "EGP",
    },
    "COPR": {
        "ticker": "COPR",
        "tv_symbol": "EGX:COPR",
        "name_en": "Copperstone Capital / Copper Co.",
        "name_ar": "النحاس المصرية / كوبر كابيتال",
        "sector": "Basic Resources & Metals",
        "sector_ar": "موارد أساسية ومعادن",
        "base_price": 0.45,
        "currency": "EGP",
    },
    "ESRS": {
        "ticker": "ESRS",
        "tv_symbol": "EGX:ESRS",
        "name_en": "Ezz Steel",
        "name_ar": "حديد عز",
        "sector": "Basic Resources",
        "sector_ar": "موارد أساسية",
        "base_price": 108.20,
        "currency": "EGP",
    },
    "ISPH": {
        "ticker": "ISPH",
        "tv_symbol": "EGX:ISPH",
        "name_en": "Ibnsina Pharma",
        "name_ar": "ابن سينا فارما",
        "sector": "Healthcare & Pharmaceuticals",
        "sector_ar": "رعاية صحية وأدوية",
        "base_price": 4.15,
        "currency": "EGP",
    },
    "EKHO": {
        "ticker": "EKHO",
        "tv_symbol": "EGX:EKHO",
        "name_en": "Egypt Kuwait Holding",
        "name_ar": "القابضة المصرية الكويتية",
        "sector": "Diversified Holdings",
        "sector_ar": "شركات قابضة متنوعة",
        "base_price": 41.50,
        "currency": "EGP",
    },
    "JUFO": {
        "ticker": "JUFO",
        "tv_symbol": "EGX:JUFO",
        "name_en": "Juhayna Food Industries",
        "name_ar": "جهينة للصناعات الغذائية",
        "sector": "Food, Beverage & Tobacco",
        "sector_ar": "أغذية ومشروبات",
        "base_price": 27.80,
        "currency": "EGP",
    },
    "PHDC": {
        "ticker": "PHDC",
        "tv_symbol": "EGX:PHDC",
        "name_en": "Palm Hills Developments",
        "name_ar": "بالم هيلز للتعمير",
        "sector": "Real Estate",
        "sector_ar": "عقارات",
        "base_price": 5.85,
        "currency": "EGP",
    },
    "HELI": {
        "ticker": "HELI",
        "tv_symbol": "EGX:HELI",
        "name_en": "Heliopolis Housing & Development",
        "name_ar": "مصر الجديدة للإسكان والتعمير",
        "sector": "Real Estate",
        "sector_ar": "عقارات",
        "base_price": 12.10,
        "currency": "EGP",
    },
    "CCAP": {
        "ticker": "CCAP",
        "tv_symbol": "EGX:CCAP",
        "name_en": "Qalaa Holdings",
        "name_ar": "شركة القلعة للاستشارات المالية",
        "sector": "Financial Services",
        "sector_ar": "خدمات مالية",
        "base_price": 3.72,
        "currency": "EGP",
    },
    "MNHD": {
        "ticker": "MNHD",
        "tv_symbol": "EGX:MASR",
        "name_en": "Madinet Masr (MNHD)",
        "name_ar": "مدينة مصر للإسكان والتعمير",
        "sector": "Real Estate",
        "sector_ar": "عقارات",
        "base_price": 4.65,
        "currency": "EGP",
    },
    "CLHO": {
        "ticker": "CLHO",
        "tv_symbol": "EGX:CLHO",
        "name_en": "Cleopatra Hospital",
        "name_ar": "مستشفى كليوباترا",
        "sector": "Healthcare & Pharmaceuticals",
        "sector_ar": "رعاية صحية وأدوية",
        "base_price": 6.90,
        "currency": "EGP",
    },
    "CIEB": {
        "ticker": "CIEB",
        "tv_symbol": "EGX:CIEB",
        "name_en": "Credit Agricole Egypt",
        "name_ar": "بنك كريدي أجريكول مصر",
        "sector": "Banking & Financial Services",
        "sector_ar": "بنوك وخدمات مالية",
        "base_price": 24.50,
        "currency": "EGP",
    },
    "ORWE": {
        "ticker": "ORWE",
        "tv_symbol": "EGX:ORWE",
        "name_en": "Oriental Weavers Carpets",
        "name_ar": "النساجون الشرقيون للسجاد",
        "sector": "Textiles & Durables",
        "sector_ar": "منسوجات وسلع معمرة",
        "base_price": 26.30,
        "currency": "EGP",
    },
    "SKPC": {
        "ticker": "SKPC",
        "tv_symbol": "EGX:SKPC",
        "name_en": "Sidi Kerir Petrochemicals",
        "name_ar": "سيدي كرير للبتروكيماويات",
        "sector": "Basic Resources & Chemicals",
        "sector_ar": "موارد أساسية وكيماويات",
        "base_price": 29.40,
        "currency": "EGP",
    },
    "ALCN": {
        "ticker": "ALCN",
        "tv_symbol": "EGX:ALCN",
        "name_en": "Alexandria Container & Cargo Handling",
        "name_ar": "الإسكندرية لتداول الحاويات والبضائع",
        "sector": "Shipping & Transportation",
        "sector_ar": "شحن ونقل",
        "base_price": 23.10,
        "currency": "EGP",
    },
    "EFIH": {
        "ticker": "EFIH",
        "tv_symbol": "EGX:EFIH",
        "name_en": "e-finance Investment Group",
        "name_ar": "إي فاينانس للاستثمارات المالية والرقمية",
        "sector": "Non-Bank Financial Services",
        "sector_ar": "خدمات مالية غير مصرفية",
        "base_price": 24.80,
        "currency": "EGP",
    },
    "DOMT": {
        "ticker": "DOMT",
        "tv_symbol": "EGX:DOMT",
        "name_en": "Arabian Food Industries (Domty)",
        "name_ar": "الصناعات الغذائية العربية (دومتي)",
        "sector": "Food & Beverage",
        "sector_ar": "أغذية ومشروبات",
        "base_price": 18.25,
        "currency": "EGP",
    },
    "RMDA": {
        "ticker": "RMDA",
        "tv_symbol": "EGX:RMDA",
        "name_en": "Rameda Pharmaceuticals",
        "name_ar": "العاشر من رمضان للصناعات الدوائية - راميدا",
        "sector": "Healthcare & Pharmaceuticals",
        "sector_ar": "رعاية صحية وأدوية",
        "base_price": 2.65,
        "currency": "EGP",
    },
    "OCDI": {
        "ticker": "OCDI",
        "tv_symbol": "EGX:OCDI",
        "name_en": "SODIC (Sixth of October Development)",
        "name_ar": "سادس من أكتوبر للتنمية والاستثمار - سوديك",
        "sector": "Real Estate",
        "sector_ar": "عقارات",
        "base_price": 49.00,
        "currency": "EGP",
    },
    "BINV": {
        "ticker": "BINV",
        "tv_symbol": "EGX:BINV",
        "name_en": "B Investments Holding",
        "name_ar": "بي إنفستمنتس القابضة",
        "sector": "Financial Services",
        "sector_ar": "خدمات مالية",
        "base_price": 21.40,
        "currency": "EGP",
    },
}

ALL_STATIC_SYMBOLS: Dict[str, Dict[str, Any]] = {**INDICES, **SEED_STOCKS}

DEFAULT_WATCHLIST: List[str] = [
    "COMI",
    "TMGH",
    "ETEL",
    "FWRY",
    "SWDY",
    "HRHO",
    "ABUK",
    "MOPCO",
    "AMOC",
    "ORAS",
    "EFID",
    "ADIB",
]


def normalize_ticker(symbol: str) -> str:
    """Strips exchange prefixes and whitespace to obtain a uniform ticker symbol.

    Args:
        symbol (str): Input symbol (e.g., 'EGX:COMI', 'comi', ' EGX:ACTF ').

    Returns:
        str: Normalized uppercase ticker (e.g., 'COMI', 'ACTF').
    """
    clean = symbol.strip().upper()
    if clean.startswith("EGX:"):
        clean = clean[4:]
    return clean


def get_static_symbol_info(ticker: str) -> Optional[Dict[str, Any]]:
    """Retrieves static metadata for a given index or seed stock.

    Args:
        ticker (str): Ticker symbol.

    Returns:
        Optional[Dict[str, Any]]: Metadata dictionary or None if not in static list.
    """
    norm = normalize_ticker(ticker)
    if norm in ALL_STATIC_SYMBOLS:
        return ALL_STATIC_SYMBOLS[norm]
    # Check alternate tv_symbol
    for s_info in ALL_STATIC_SYMBOLS.values():
        if s_info.get("tv_symbol", "").upper().endswith(f":{norm}"):
            return s_info
    return None
