"""Official Environment Canada alerts (warnings/watches/advisories/statements).

No heavy dependencies - fetches ECCC's public CityPage Weather XML with requests
and parses it with the stdlib. It first resolves Killarney's ECCC site code from
the official siteList, then reads that site's warnings. Returns:
  - a formatted string of active official alerts, or
  - "no active alerts" text if the feed was read but nothing is active, or
  - None if ECCC couldn't be reached/resolved (caller then falls back to the
    forecast-based watch in openmeteo.alerts()).

Data source: Environment and Climate Change Canada (weather.gc.ca).
"""
import logging
import math
import xml.etree.ElementTree as ET

import requests

import config
import util
from cache import cache

log = logging.getLogger(__name__)

SITELIST_URL = "https://dd.weather.gc.ca/citypage_weather/xml/siteList.xml"
CITYPAGE_URL = "https://dd.weather.gc.ca/citypage_weather/xml/{prov}/{code}_e.xml"
SITELIST_TTL = 86400   # 24h - site codes rarely change
WARN_TTL = 600         # 10 min
_HEADERS = {"User-Agent": config.USER_AGENT}

# alert event types we treat as active (skip "ended" notices)
_ACTIVE = ("warning", "watch", "advisory", "statement")


def _get_text(url, ttl, cache_key):
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    resp = requests.get(url, headers=_HEADERS, timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()
    text = resp.text
    cache.set(cache_key, text, ttl)
    return text


def _parse_coord(raw):
    """'46.01N' / '81.40W' -> signed float."""
    if not raw:
        return None
    raw = raw.strip()
    sign = -1 if raw[-1] in ("S", "W") else 1
    num = raw[:-1] if raw[-1] in ("N", "S", "E", "W") else raw
    try:
        return sign * float(num)
    except ValueError:
        return None


def _resolve_site():
    """Find Killarney's ECCC (provinceCode, siteCode). Cached. None on failure."""
    cached = cache.get("eccc_site")
    if cached is not None:
        return cached
    xml = _get_text(SITELIST_URL, SITELIST_TTL, "eccc_sitelist")
    root = ET.fromstring(xml)

    name_match = None
    nearest = None
    nearest_dist = float("inf")
    for site in root.findall("site"):
        code = site.get("code")
        prov = (site.findtext("provinceCode") or "").strip()
        name = (site.findtext("nameEn") or "").strip()
        if not code or not prov:
            continue
        # prefer an exact Ontario "Killarney" name match
        if prov == "ON" and "killarney" in name.lower():
            name_match = (prov, code, name)
            break
        lat = _parse_coord(site.findtext("latitude"))
        lon = _parse_coord(site.findtext("longitude"))
        if lat is not None and lon is not None:
            d = _haversine(config.KILLARNEY_LAT, config.KILLARNEY_LON, lat, lon)
            if d < nearest_dist:
                nearest_dist, nearest = d, (prov, code, name)

    site = name_match or nearest
    if site:
        cache.set("eccc_site", site, SITELIST_TTL)
    return site


def _haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _issue_time(event):
    for dt in event.findall("dateTime"):
        summary = dt.findtext("textSummary")
        if summary:
            return summary.strip()
    return ""


def _parse_alerts(citypage_xml):
    """-> list of 'HEADLINE (issued ...)' strings for active alerts."""
    root = ET.fromstring(citypage_xml)
    warnings = root.find("warnings")
    if warnings is None:
        return []
    out = []
    for event in warnings.findall("event"):
        etype = (event.get("type") or "").lower()
        desc = (event.get("description") or "").strip()
        low = desc.lower()
        if "ended" in low or etype == "ended":
            continue
        if etype not in _ACTIVE and not any(k in low for k in _ACTIVE):
            continue
        when = _issue_time(event)
        out.append(f"{desc.upper()}" + (f" (issued {when})" if when else ""))
    return out


def alerts():
    """Official ECCC alerts string, or None if ECCC couldn't be reached."""
    try:
        site = _resolve_site()
        if not site:
            return None
        prov, code, _name = site
        xml = _get_text(CITYPAGE_URL.format(prov=prov, code=code),
                        WARN_TTL, f"eccc_warn:{code}")
        active = _parse_alerts(xml)
    except Exception as exc:
        log.warning("ECCC alerts unavailable (%s)", exc)
        return None

    if not active:
        return f"{config.LOCATION_NAME}: no active ECCC alerts (official)."
    body = "; ".join(active)
    return f"ECCC ALERT - {config.LOCATION_NAME}: {body}. Full text: weather.gc.ca"


def banner():
    """Short one-line official-alert banner for TODAY, or '' if none/unavailable."""
    try:
        site = _resolve_site()
        if not site:
            return ""
        prov, code, _name = site
        xml = _get_text(CITYPAGE_URL.format(prov=prov, code=code),
                        WARN_TTL, f"eccc_warn:{code}")
        active = _parse_alerts(xml)
    except Exception:
        return ""
    if not active:
        return ""
    first = active[0].split(" (issued")[0]
    extra = f" (+{len(active) - 1} more)" if len(active) > 1 else ""
    return f"ECCC ALERT: {first}{extra}"
