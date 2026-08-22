"""Official Environment Canada alerts via the weather.gc.ca ATOM alert feed.

One stable, coordinate-keyed URL (no dated folders, site codes, or timestamps):
  https://weather.gc.ca/rss/alerts/<lat>_<lon>_e.xml

It's an ATOM feed whose <entry> items are the active warnings/watches/advisories/
statements for that point, each with a title, category, summary, and issue time.
Parsed with the stdlib (no heavy deps). Returns:
  - a formatted string of active official alerts, or
  - "no active alerts" text if the feed was read but nothing is active, or
  - None if the feed couldn't be reached (caller falls back to the forecast
    watch in openmeteo.alerts()).

Data source: Environment and Climate Change Canada (weather.gc.ca).
"""
import logging
import re
import xml.etree.ElementTree as ET

import requests

import config
import util
from cache import cache

log = logging.getLogger(__name__)

# feed uses the same coords as the weather.gc.ca page for Killarney PP
_LAT = getattr(config, "ECCC_LAT", 46.101)
_LON = getattr(config, "ECCC_LON", -81.381)
URL = f"https://weather.gc.ca/rss/alerts/{_LAT:.3f}_{_LON:.3f}_e.xml"
TTL = 600  # 10 min
_HEADERS = {"User-Agent": config.USER_AGENT}
_ATOM = "{http://www.w3.org/2005/Atom}"

# entries whose title is one of these mean "all clear" - not an active alert
_NO_ALERT = ("no watches or warnings", "no alerts", "aucune veille")


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")            # strip any HTML
    return re.sub(r"\s+", " ", text).strip()


def _fetch_entries():
    cached = cache.get("eccc_alert_xml")
    if cached is None:
        resp = requests.get(URL, headers=_HEADERS, timeout=config.HTTP_TIMEOUT)
        resp.raise_for_status()
        cached = resp.text
        cache.set("eccc_alert_xml", cached, TTL)
    root = ET.fromstring(cached)

    alerts = []
    for entry in root.findall(f"{_ATOM}entry"):
        title = _clean(entry.findtext(f"{_ATOM}title"))
        if not title or any(k in title.lower() for k in _NO_ALERT):
            continue
        summary = _clean(entry.findtext(f"{_ATOM}summary"))
        alerts.append((title, summary))
    return alerts


def alerts():
    """Official ECCC alerts string, or None if the feed couldn't be reached."""
    try:
        active = _fetch_entries()
    except Exception as exc:
        log.warning("ECCC alerts unavailable (%s)", exc)
        return None
    if not active:
        return f"{config.LOCATION_NAME}: no active ECCC alerts (official)."
    parts = []
    for title, summary in active:
        # title already names the alert + place; append the summary if it adds info
        parts.append(f"{title}. {summary}" if summary else title)
    body = " || ".join(parts)
    return f"ECCC ALERT: {body} (weather.gc.ca)"


def banner():
    """One-line official-alert banner for TODAY, or '' if none/unavailable."""
    try:
        active = _fetch_entries()
    except Exception:
        return ""
    if not active:
        return ""
    first = active[0][0]
    extra = f" (+{len(active) - 1} more)" if len(active) > 1 else ""
    return f"ECCC ALERT: {first}{extra}"
