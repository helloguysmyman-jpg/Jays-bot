"""Shared helpers: Eastern Time conversion and small formatting utilities."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import config

ET = ZoneInfo(config.TIMEZONE)


def now_et():
    """Current time as an aware datetime in Eastern Time."""
    return datetime.now(ET)


def parse_utc(iso_str):
    """Parse an MLB ISO timestamp (e.g. '2026-08-22T23:07:00Z') as aware UTC."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def to_et(dt):
    """Convert an aware datetime to Eastern Time (or None)."""
    return dt.astimezone(ET) if dt else None


def fmt_time_et(dt):
    """Format an aware datetime as '7:07 PM ET' (cross-platform, no leading 0)."""
    et = to_et(dt)
    if not et:
        return "TBD"
    hour12 = et.hour % 12 or 12
    ampm = "AM" if et.hour < 12 else "PM"
    return f"{hour12}:{et.minute:02d} {ampm} ET"


def fmt_day_et(dt):
    """Format an aware datetime as 'Fri Aug 22' (no leading zero on day)."""
    et = to_et(dt)
    if not et:
        return "TBD"
    return et.strftime("%a %b ") + str(et.day)


def parse_local_date(date_str):
    """Parse an Open-Meteo daily date string 'YYYY-MM-DD' to a date."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def round_num(x):
    """Round to a whole number, tolerating None."""
    return None if x is None else int(round(x))
