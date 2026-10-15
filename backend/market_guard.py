"""
Market Hours Guard for Egyptian Exchange (EGX).
Checks Africa/Cairo timezone:
- Active Days: Sunday through Thursday (Friday & Saturday are Egyptian weekend).
- Active Trading Hours: 10:00 to 14:30 Cairo Time.
"""

from datetime import datetime, time, timedelta
from typing import Dict, Any
import pytz
from config import settings

CAIRO_TZ = pytz.timezone(settings.MARKET_TIMEZONE)

def get_cairo_now() -> datetime:
    """Return the current datetime localized to Africa/Cairo."""
    return datetime.now(CAIRO_TZ)

def check_market_hours(current_dt: datetime = None) -> Dict[str, Any]:
    """
    Check if Egyptian Exchange is currently open.
    EGX is open Sunday - Thursday, 10:00 to 14:30 Cairo time.
    """
    if current_dt is None:
        current_dt = get_cairo_now()
    elif current_dt.tzinfo is None:
        current_dt = CAIRO_TZ.localize(current_dt)
    else:
        current_dt = current_dt.astimezone(CAIRO_TZ)

    # In Python: Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
    weekday = current_dt.weekday()
    is_trading_day = weekday in (6, 0, 1, 2, 3)  # Sun, Mon, Tue, Wed, Thu

    market_open_time = time(settings.MARKET_OPEN_HOUR, settings.MARKET_OPEN_MINUTE)
    market_close_time = time(settings.MARKET_CLOSE_HOUR, settings.MARKET_CLOSE_MINUTE)
    current_time = current_dt.time()

    is_open = False
    status_label = "CLOSED"
    message = "Market is closed."

    if not is_trading_day:
        status_label = "WEEKEND"
        day_name = current_dt.strftime("%A")
        message = f"Egyptian Exchange is closed for the weekend ({day_name})."
    else:
        if current_time < market_open_time:
            status_label = "PRE_MARKET"
            message = "Pre-market session. Regular trading begins at 10:00 AM Cairo time."
        elif market_open_time <= current_time <= market_close_time:
            is_open = True
            status_label = "OPEN"
            message = "Live session active (10:00 - 14:30 Cairo time)."
        else:
            status_label = "CLOSED"
            message = "Market closed for today. Regular session ends at 14:30 Cairo time."

    # Next session calculation
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
    """Calculate the next upcoming market open datetime in Cairo."""
    candidate = current_dt.replace(
        hour=settings.MARKET_OPEN_HOUR,
        minute=settings.MARKET_OPEN_MINUTE,
        second=0,
        microsecond=0
    )
    if candidate <= current_dt or current_dt.weekday() in (4, 5):
        # Move forward day by day until we find a trading day
        candidate += timedelta(days=1)
        while candidate.weekday() in (4, 5):  # Skip Friday and Saturday
            candidate += timedelta(days=1)
        candidate = candidate.replace(
            hour=settings.MARKET_OPEN_HOUR,
            minute=settings.MARKET_OPEN_MINUTE,
            second=0,
            microsecond=0
        )
    return candidate
