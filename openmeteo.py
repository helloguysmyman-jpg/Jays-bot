"""All Killarney PP weather via Open-Meteo (free, no key, no heavy deps).

Covers current conditions, a 24h hourly strip, worded today/tonight, a 3-day
outlook, and a forecast-based severe-weather watch. Open-Meteo does not carry
official government warnings, so ALERTS is derived from the forecast (thunder,
heavy precip, strong wind, freezing) and is clearly labelled as such - not an
official Environment Canada warning. Data source: Open-Meteo.com (CC BY 4.0).
"""
import logging
import time

import requests

import config
import util
from cache import cache

log = logging.getLogger(__name__)

URL = "https://api.open-meteo.com/v1/forecast"
TTL = 1200          # 20 min: one fetch serves many commands
STALE_TTL = 21600   # keep a last-good copy up to 6h to survive rate-limit blips
_HEADERS = {"User-Agent": config.USER_AGENT}

WMO = {
    0: "Clear", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle",
    55: "Heavy drizzle", 56: "Freezing drizzle", 57: "Freezing drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain", 66: "Freezing rain",
    67: "Freezing rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Light showers", 81: "Showers", 82: "Heavy showers",
    85: "Snow showers", 86: "Snow showers", 95: "Thunderstorm",
    96: "Thunderstorm+hail", 99: "Thunderstorm+hail",
}
WMO_SHORT = {
    0: "clear", 1: "clear", 2: "pt cloud", 3: "cloud", 45: "fog", 48: "fog",
    51: "drizzle", 53: "drizzle", 55: "drizzle", 56: "frz driz", 57: "frz driz",
    61: "rain", 63: "rain", 65: "hvy rain", 66: "frz rain", 67: "frz rain",
    71: "snow", 73: "snow", 75: "hvy snow", 77: "snow", 80: "showers",
    81: "showers", 82: "hvy shwr", 85: "snow shwr", 86: "snow shwr",
    95: "storm", 96: "storm", 99: "storm",
}
COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def _fetch():
    cached = cache.get("openmeteo")
    if cached is not None:
        return cached
    params = {
        "latitude": config.KILLARNEY_LAT,
        "longitude": config.KILLARNEY_LON,
        "timezone": config.TIMEZONE,
        "current": ("temperature_2m,apparent_temperature,precipitation,"
                    "weather_code,wind_speed_10m,wind_direction_10m"),
        "hourly": ("precipitation_probability,precipitation,weather_code,"
                   "temperature_2m,wind_speed_10m,wind_gusts_10m"),
        "daily": ("weather_code,temperature_2m_max,temperature_2m_min,"
                  "precipitation_probability_max"),
        "forecast_days": 4,
        "wind_speed_unit": "kmh",
        # Use Environment Canada's model (incl. the 2.5km HRDPS for Ontario) so
        # readings line up with weather.gc.ca / Canadian weather apps rather than
        # a coarse global model that misses local precip.
        "models": "gem_seamless",
    }
    for attempt in range(2):
        try:
            resp = requests.get(URL, params=params, headers=_HEADERS,
                                timeout=config.HTTP_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            cache.set("openmeteo", data, TTL)
            cache.set("openmeteo_stale", data, STALE_TTL)
            return data
        except Exception as exc:
            if attempt == 0:
                time.sleep(1.2)  # brief backoff, then one retry
                continue
            # On repeated failure (e.g. a shared-IP 429 on Railway), serve the
            # last good reading if we have one - stale weather beats none.
            stale = cache.get("openmeteo_stale")
            if stale is not None:
                log.warning("open-meteo fetch failed (%s); serving stale data", exc)
                return stale
            raise


def _compass(deg):
    return "" if deg is None else COMPASS[round(deg / 45) % 8]


def _hour_index(data):
    times = data.get("hourly", {}).get("time", [])
    if not times:
        return None
    now = util.now_et().strftime("%Y-%m-%dT%H:00")
    if now in times:
        return times.index(now)
    for i, t in enumerate(times):
        if t >= now:
            return i
    return None


def _hhmm(iso):
    hh = int(iso[11:13])
    return f"{hh % 12 or 12}{'AM' if hh < 12 else 'PM'}"


def _at(arr, i):
    return arr[i] if arr and i is not None and i < len(arr) else None


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------
def current_weather():
    """NOW - current temp, feels-like, conditions, wind, rain chance."""
    data = _fetch()
    cur = data.get("current", {})
    temp = util.round_num(cur.get("temperature_2m"))
    feels = util.round_num(cur.get("apparent_temperature"))
    cond = WMO.get(cur.get("weather_code"), "Unknown")
    wind = util.round_num(cur.get("wind_speed_10m"))
    wdir = _compass(cur.get("wind_direction_10m"))
    pop = _at(data.get("hourly", {}).get("precipitation_probability", []), _hour_index(data))
    head = f"{config.LOCATION_NAME}: {temp}C"
    if feels is not None and feels != temp:
        head += f" (feels {feels})"
    segs = [f"{head}, {cond}", f"Wind {wind} km/h {wdir}".strip()]
    if pop is not None:
        segs.append(f"Rain {pop}%")
    return ". ".join(segs) + "."


def hourly_24():
    """HOURLY - next 24h in 3-hour steps: time, temp, rain chance."""
    data = _fetch()
    i = _hour_index(data)
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    pops = hourly.get("precipitation_probability", [])
    if i is None or not times:
        return "Hourly data unavailable right now."
    pts = []
    for j in range(i, min(i + 24, len(times)), 3):
        pts.append(f"{_hhmm(times[j])} {util.round_num(_at(temps, j))}C {_at(pops, j)}%")
    return f"{config.LOCATION_NAME} 24h (temp/rain): " + " | ".join(pts)


def _overnight_code(data):
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    codes = hourly.get("weather_code", [])
    now = util.now_et().strftime("%Y-%m-%dT%H:00")
    for i, t in enumerate(times):
        if t.endswith("T00:00") and t > now and i < len(codes):
            return codes[i]
    return None


def today():
    """TODAY - worded today + tonight, with a severe-weather banner if any."""
    data = _fetch()
    daily = data.get("daily", {})
    codes = daily.get("weather_code", [])
    hi = daily.get("temperature_2m_max", [])
    lo = daily.get("temperature_2m_min", [])
    pops = daily.get("precipitation_probability_max", [])
    if not codes:
        return "Forecast unavailable right now."
    day_cond = WMO.get(codes[0], "?")
    night_cond = WMO.get(_overnight_code(data), day_cond)
    pop = _at(pops, 0)
    lines = [f"Today: {day_cond}. High {util.round_num(_at(hi, 0))}."
             + (f" Rain {pop}%." if pop is not None else ""),
             f"Tonight: {night_cond}. Low {util.round_num(_at(lo, 0))}."]
    banner = _alert_banner(data)
    body = "\n".join(lines)
    return f"{banner}\n{body}" if banner else body


def forecast():
    """FORECAST - compact next-3-day outlook."""
    data = _fetch()
    daily = data.get("daily", {})
    times = daily.get("time", [])
    codes = daily.get("weather_code", [])
    tmax = daily.get("temperature_2m_max", [])
    tmin = daily.get("temperature_2m_min", [])
    pops = daily.get("precipitation_probability_max", [])
    if not times:
        return "Forecast unavailable right now."
    pieces = []
    for i in range(min(3, len(times))):
        try:
            label = util.parse_local_date(times[i]).strftime("%a")
        except ValueError:
            label = times[i]
        cond = WMO_SHORT.get(_at(codes, i), "")
        piece = f"{label} {cond} {util.round_num(_at(tmax, i))}/{util.round_num(_at(tmin, i))}"
        pop = _at(pops, i)
        if pop is not None:
            piece += f" {pop}%"
        pieces.append(piece)
    return f"{config.LOCATION_NAME} 3-day: " + " | ".join(pieces)


# --------------------------------------------------------------------------
# Forecast-based severe-weather watch (NOT an official ECCC warning)
# --------------------------------------------------------------------------
def _severe_events(data):
    i = _hour_index(data)
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    if i is None or not times:
        return []
    window = list(range(i, min(i + 24, len(times))))
    codes = hourly.get("weather_code", [])
    gusts = hourly.get("wind_gusts_10m", [])
    winds = hourly.get("wind_speed_10m", [])

    def hits(codeset):
        return [j for j in window if _at(codes, j) in codeset]

    events = []
    for label, codeset in (("Thunderstorms", {95, 96, 99}),
                           ("Heavy rain", {65, 82}),
                           ("Heavy snow", {75, 86}),
                           ("Freezing rain", {56, 57, 66, 67})):
        h = hits(codeset)
        if h:
            events.append((label, h))
    windy = [j for j in window if (_at(gusts, j) or _at(winds, j) or 0) >= 60]
    if windy:
        events.append(("Strong winds", windy))
    return events


def _span(times, h):
    if h[-1] + 1 < len(times):
        return f"{_hhmm(times[h[0]])}-{_hhmm(times[h[-1] + 1])}"
    return f"from {_hhmm(times[h[0]])}"


def _alert_banner(data):
    events = _severe_events(data)
    if not events:
        return ""
    label = events[0][0]
    extra = f" (+{len(events) - 1} more)" if len(events) > 1 else ""
    return f"WATCH: {label}{extra} - forecast-based, not an official warning"


def alerts():
    """ALERTS - forecast-based severe-weather watch for the next 24h."""
    data = _fetch()
    events = _severe_events(data)
    times = data.get("hourly", {}).get("time", [])
    if not events:
        return f"{config.LOCATION_NAME}: no severe weather in next 24h (forecast-based)."
    parts = [f"{label} {_span(times, h)}" for label, h in events]
    return (f"{config.LOCATION_NAME} watch (forecast-based): " + "; ".join(parts)
            + ". Not an official ECCC warning - check weather.gc.ca for those.")
