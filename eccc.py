"""Environment Canada (official) data for Killarney via the env_canada library.

Provides the worded day/night forecast ("Today: Sunny. High 24.") and
official warnings/watches/advisories, which Open-Meteo cannot. env_canada
resolves the nearest ECCC station from the coordinates and keeps working
through ECCC's file-URL changes.

The library is async; we call it with asyncio.run() (fine under a sync
gunicorn worker) and cache the result. Everything is wrapped so an outage
degrades to a short message instead of a crash.
"""
import asyncio
import logging

import config
from cache import cache

log = logging.getLogger(__name__)

TTL = 600  # 10 minutes
_ALERT_CATEGORIES = ("warnings", "watches", "advisories")


def _fetch():
    """Return {'daily': [...], 'alerts': {...}} from ECCC, cached."""
    cached = cache.get("eccc")
    if cached is not None:
        return cached
    from env_canada import ECWeather  # imported lazily (heavy dependency)

    ec = ECWeather(coordinates=(config.KILLARNEY_LAT, config.KILLARNEY_LON),
                   language="english")
    asyncio.run(ec.update())
    data = {
        "daily": ec.daily_forecasts or [],
        "alerts": ec.alerts or {},
        "station": ec.station_id,
    }
    cache.set("eccc", data, TTL)
    return data


def _active_alerts(alerts):
    """Flatten warnings/watches/advisories into (label, title, date) tuples."""
    out = []
    for key in _ALERT_CATEGORIES:
        cat = alerts.get(key, {}) or {}
        for item in cat.get("value", []) or []:
            out.append((cat.get("label", key.title()),
                        item.get("title", "").strip(),
                        (item.get("date") or "").strip()))
    return out


def _alert_flag(alerts):
    """A one-line ALERT banner if any warning/watch/advisory is active."""
    active = _active_alerts(alerts)
    if not active:
        return ""
    label, title, _ = active[0]
    extra = f" (+{len(active) - 1} more)" if len(active) > 1 else ""
    return f"\u26A0\uFE0F ALERT {label.upper()}: {title}{extra}"


def today():
    """TODAY - Environment Canada worded day + night forecast (+ alert banner)."""
    data = _fetch()
    daily = data.get("daily", [])
    if not daily:
        return "Forecast unavailable right now."
    lines = []
    for idx, period in enumerate(daily[:2]):  # e.g. Today + Tonight
        name = period.get("period", "")
        text = period.get("text_summary", "")
        tag = "\U0001F4C5 " if idx == 0 else ""
        lines.append(f"{tag}{name}: {text}".strip(": "))
    flag = _alert_flag(data.get("alerts", {}))
    body = "\n".join(lines)
    return f"{flag}\n{body}" if flag else body


def forecast():
    """FORECAST - Environment Canada worded outlook, next several day/night periods."""
    data = _fetch()
    daily = data.get("daily", [])
    if not daily:
        return "Forecast unavailable right now."
    lines = [f"\U0001F4C5 {config.LOCATION_NAME} forecast:"]
    for period in daily[:6]:  # ~3 days of day/night periods
        name = period.get("period", "")
        text = period.get("text_summary", "")
        lines.append(f"{name}: {text}".strip(": "))
    return "\n".join(lines)


def alerts():
    """ALERTS - active Environment Canada warnings/watches/advisories."""
    data = _fetch()
    active = _active_alerts(data.get("alerts", {}))
    if not active:
        return f"\u2705 No active alerts for {config.LOCATION_NAME} area."
    lines = [f"\u26A0\uFE0F ALERTS ({config.LOCATION_NAME} area):"]
    for label, title, date in active:
        when = f" - {date}" if date else ""
        lines.append(f"{label.upper()}: {title}{when}")
    return "\n".join(lines)
