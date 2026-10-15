"""Market Hours Guard and Egyptian Exchange (EGX) Schedule Evaluator.

The Egyptian Exchange operates under specific Middle Eastern market conventions:
- Trading Week: Sunday through Thursday (Friday and Saturday are the official weekend).
- Main Trading Session: 10:00 to 14:30 Cairo Local Time (Africa/Cairo timezone).
- Pre-Market Session: 09:30 to 10:00 Cairo Local Time.

Outside active market hours or on weekends, this module signals the system to
fetch closing snapshots once rather than streaming continuously, reducing CPU
and network overhead.

Typical usage example:
    from app.market_guard import check_market_hours
    status = check_market_hours()
    if status["is_open"]:
        print("Market is live!")
"""

from datetime import datetime, time, timedelta
from typing import Dict, Any, Optional
import pytz
from app.config import settings

# Egyptian standard timezone
CAIRO_TZ = pytz.timezone(settings.MARKET_TIMEZONE)


def get_cairo_now() -> datetime:
    """Returns the current timestamp accurately localized to Africa/Cairo.

    Returns:
        datetime: Timezone-aware datetime representing current time in Cairo.
    """
    return datetime.now(CAIRO_TZ)


def check_market_hours(current_dt: Optional[datetime] = None) -> Dict[str, Any]:
    """Evaluates whether the Egyptian Exchange is open, in pre-market, or closed.

    Python weekday conventions:
        Monday = 0, Tuesday = 1, Wednesday = 2, Thursday = 3,
        Friday = 4, Saturday = 5, Sunday = 6.
    EGX trading days are: Sunday (6), Monday (0), Tuesday (1), Wednesday (2), Thursday (3).
    Weekend days are: Friday (4) and Saturday (5).

    Args:
        current_dt (Optional[datetime]): Timestamp to check. If None, uses get_cairo_now().

    Returns:
        Dict[str, Any]: Detailed status payload including:
            - is_open (bool): True if regular session is active.
            - status (str): 'OPEN', 'CLOSED', 'WEEKEND', or 'PRE_MARKET'.
            - message (str): Human-readable session notice in English.
            - cairo_time (str): Formatted current Cairo time (YYYY-MM-DD HH:MM:SS).
            - next_open (str): Formatted expected timestamp of next market opening.
            - trading_days (str): 'Sun - Thu'.
            - trading_hours (str): '10:00 - 14:30 Cairo'.
    """
    if current_dt is None:
        current_dt = get_cairo_now()
    elif current_dt.tzinfo is None:
        current_dt = CAIRO_TZ.localize(current_dt)
    else:
        current_dt = current_dt.astimezone(CAIRO_TZ)

    weekday = current_dt.weekday()
    is_trading_day = weekday in (6, 0, 1, 2, 3)

    market_open_time = time(settings.MARKET_OPEN_HOUR, settings.MARKET_OPEN_MINUTE)
    market_close_time = time(settings.MARKET_CLOSE_HOUR, settings.MARKET_CLOSE_MINUTE)
    current_time = current_dt.time()

    is_open = False
    status_label = "CLOSED"
    message = "Market is closed."

    if not is_trading_day:
        status_label = "WEEKEND"
        day_name = current_dt.strftime("%A")
        message = f"Egyptian Exchange is closed for the weekend ({day_name}). Regular trading resumes Sunday at 10:00 AM Cairo."
    else:
        if current_time < market_open_time:
            status_label = "PRE_MARKET"
            message = "Pre-market session. Regular continuous trading begins at 10:00 AM Cairo."
        elif market_open_time <= current_time <= market_close_time:
            is_open = True
            status_label = "OPEN"
            message = "Live session active (10:00 - 14:30 Cairo time)."
        else:
            status_label = "CLOSED"
            message = "Market closed for today. Regular session ended at 14:30 Cairo time."

    next_open = get_next_market_open(current_dt)

    return {
        "is_open": is_open,
        "status": status_label,
        "message": message,
        "cairo_time": current_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": settings.MARKET_TIMEZONE,
        "next_open": next_open.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "trading_days": "Sun - Thu",
        "trading_hours": f"{settings.MARKET_OPEN_HOUR:02d}:{settings.MARKET_OPEN_MINUTE:02d} - {settings.MARKET_CLOSE_HOUR:02d}:{settings.MARKET_CLOSE_MINUTE:02d} Cairo",
    }


def get_next_market_open(current_dt: datetime) -> datetime:
    """Calculates the upcoming regular session opening timestamp in Cairo.

    Args:
        current_dt (datetime): Starting reference timestamp.

    Returns:
        datetime: Upcoming market opening timestamp in Africa/Cairo.
    """
    candidate = current_dt.replace(
        hour=settings.MARKET_OPEN_HOUR,
        minute=settings.MARKET_OPEN_MINUTE,
        second=0,
        microsecond=0,
    )

    # If open time has already passed today, or today is a weekend, advance to next trading day
    if candidate <= current_dt or current_dt.weekday() in (4, 5):
        candidate += timedelta(days=1)
        while candidate.weekday() in (4, 5):  # Skip Friday (4) and Saturday (5)
            candidate += timedelta(days=1)
        candidate = candidate.replace(
            hour=settings.MARKET_OPEN_HOUR,
            minute=settings.MARKET_OPEN_MINUTE,
            second=0,
            microsecond=0,
        )

    return candidate
