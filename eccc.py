"""Official Environment Canada alerts via the weather.gc.ca ATOM alert feed.

One stable, coordinate-keyed URL (no dated folders, site codes, or timestamps):
  https://weather.gc.ca/rss/alerts/<lat>_<lon>_e.xml

The ATOM feed lists the active warnings/watches/advisories/statements, but its
<summary> is only a generic sentence. The full body (hazard, timing, safety
advice) lives on the linked report page, so for the top alert we also fetch that
HTML report and extract the statement text. If that scrape fails or looks wrong,
we fall back to the feed summary - ALERTS never regresses.

Returns a formatted alert string, an "all clear" line, or None if unreachable
(caller then falls back to openmeteo.alerts()).
Data source: Environment and Climate Change Canada (weather.gc.ca).
"""
import html as _html
import logging
import re
import xml.etree.ElementTree as ET

import requests

import config
import util
from cache import cache

log = logging.getLogger(__name__)

_LAT = getattr(config, "ECCC_LAT", 46.101)
_LON = getattr(config, "ECCC_LON", -81.381)
URL = f"https://weather.gc.ca/rss/alerts/{_LAT:.3f}_{_LON:.3f}_e.xml"
TTL = 600
REPORT_TTL = 600
MAX_LEN = 1100  # cap the body so ALERTS doesn't run to absurd length
_HEADERS = {"User-Agent": config.USER_AGENT}
_ATOM = "{http://www.w3.org/2005/Atom}"

_NO_ALERT = ("no watches or warnings", "no alerts", "aucune veille")
_END_MARKERS = ("in effect for", "date modified", "report a typo",
                "related links", "follow:", "print instructions")


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _get(url, cache_key, ttl):
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    resp = requests.get(url, headers=_HEADERS, timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()
    cache.set(cache_key, resp.text, ttl)
    return resp.text


def _entries():
    """Active alerts as list of {title, summary, link}. Raises on fetch fail."""
    xml = _get(URL, "eccc_alert_xml", TTL)
    root = ET.fromstring(xml)
    out = []
    for entry in root.findall(f"{_ATOM}entry"):
        title = _clean(entry.findtext(f"{_ATOM}title"))
        if not title or any(k in title.lower() for k in _NO_ALERT):
            continue
        summary = _clean(entry.findtext(f"{_ATOM}summary"))
        link = ""
        for ln in entry.findall(f"{_ATOM}link"):
            href = ln.get("href", "")
            if (ln.get("type") or "").endswith("html") and href:
                link = href
                break
            if href and not link:
                link = href
        out.append({"title": title, "summary": summary, "link": link})
    return out


def _extract_body(html_text, alert_type):
    """Pull the statement body out of the HTML report page. '' if not found."""
    h = re.sub(r"(?i)<br\s*/?>", "\n", html_text)
    h = re.sub(r"(?i)</(p|div|li|tr|h[1-6]|section)>", "\n", h)
    text = _html.unescape(re.sub(r"<[^>]+>", " ", h))
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    text = "\n".join(ln for ln in lines if ln)

    start = 0
    if alert_type:
        i = text.lower().find(alert_type.lower())
        if i != -1:
            start = i + len(alert_type)
    body = text[start:]

    low = body.lower()
    cut = len(body)
    for marker in _END_MARKERS:
        j = low.find(marker)
        if j != -1:
            cut = min(cut, j)
    body = body[:cut].strip(" \n:-")
    body = re.sub(r"\n{2,}", "\n", body).strip()

    # sanity check: must look like real prose, not stray markup/nav
    if len(body) < 40 or "." not in body or " " not in body:
        return ""
    if len(body) > MAX_LEN:
        clip = body[:MAX_LEN]
        dot = clip.rfind(".")
        body = (clip[:dot + 1] if dot > 200 else clip) + " ...(full at weather.gc.ca)"
    return body


def _report_body(entry):
    if not entry.get("link"):
        return ""
    try:
        html_text = _get(entry["link"], f"eccc_report:{entry['link']}", REPORT_TTL)
    except Exception as exc:
        log.warning("ECCC report fetch failed (%s)", exc)
        return ""
    alert_type = entry["title"].split(",")[0].strip()  # e.g. "SPECIAL WEATHER STATEMENT"
    return _extract_body(html_text, alert_type)


def alerts():
    """Official ECCC alerts (full text for the top one), or None if unreachable."""
    try:
        active = _entries()
    except Exception as exc:
        log.warning("ECCC alerts unavailable (%s)", exc)
        return None
    if not active:
        return f"{config.LOCATION_NAME}: no active ECCC alerts (official)."

    top = active[0]
    body = _report_body(top) or top["summary"] or ""
    text = f"ECCC ALERT - {top['title']}:\n{body}".rstrip()
    if len(active) > 1:
        others = "; ".join(a["title"].split(",")[0].strip() for a in active[1:])
        text += f"\nAlso active: {others}."
    return text + "\n(weather.gc.ca)"


def banner():
    """One-line official-alert banner for TODAY, or '' if none/unavailable."""
    try:
        active = _entries()
    except Exception:
        return ""
    if not active:
        return ""
    first = active[0]["title"].split(",")[0].strip()
    extra = f" (+{len(active) - 1} more)" if len(active) > 1 else ""
    return f"ECCC ALERT: {first}{extra}"
