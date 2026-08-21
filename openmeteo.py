"""Current conditions + 24h hourly strip for Killarney PP via Open-Meteo.

Free, no key. Open-Meteo is used for the quantitative pieces (now-cast and
the hourly temperature/rain strip); the worded day/night forecast and
official warnings come from Environment Canada (see eccc.py).
Data source: Open-Meteo.com (CC BY 4.0).
"""
import logging

import requests

import config, util
from cache import cache

log = logging.getLogger(__name__)

URL = "https://api.open-meteo.com/v1/forecast"
TTL = 600  # 10 minutes
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
COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

# WMO weather code -> emoji
EMOJI = {
    0: "\u2600\uFE0F", 1: "\U0001F324\uFE0F", 2: "\u26C5", 3: "\u2601\uFE0F",
    45: "\U0001F32B\uFE0F", 48: "\U0001F32B\uFE0F",
    51: "\U0001F327\uFE0F", 53: "\U0001F327\uFE0F", 55: "\U0001F327\uFE0F",
    56: "\U0001F327\uFE0F", 57: "\U0001F327\uFE0F",
    61: "\U0001F327\uFE0F", 63: "\U0001F327\uFE0F", 65: "\U0001F327\uFE0F",
    66: "\U0001F327\uFE0F", 67: "\U0001F327\uFE0F",
    71: "\u2744\uFE0F", 73: "\u2744\uFE0F", 75: "\u2744\uFE0F", 77: "\u2744\uFE0F",
    80: "\U0001F326\uFE0F", 81: "\U0001F327\uFE0F", 82: "\u26C8\uFE0F",
    85: "\U0001F328\uFE0F", 86: "\U0001F328\uFE0F",
    95: "\u26C8\uFE0F", 96: "\u26C8\uFE0F", 99: "\u26C8\uFE0F",
}


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
        "hourly": "precipitation_probability,weather_code,temperature_2m",
        "forecast_days": 2,
        "wind_speed_unit": "kmh",
    }
    resp = requests.get(URL, params=params, headers=_HEADERS,
                        timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    cache.set("openmeteo", data, TTL)
    return data


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


def current_weather():
    """NOW - current temp, feels-like, conditions, wind, rain chance."""
    data = _fetch()
    cur = data.get("current", {})
    temp = util.round_num(cur.get("temperature_2m"))
    feels = util.round_num(cur.get("apparent_temperature"))
    cond = WMO.get(cur.get("weather_code"), "Unknown")
    wind = util.round_num(cur.get("wind_speed_10m"))
    wdir = _compass(cur.get("wind_direction_10m"))
    i = _hour_index(data)
    pops = data.get("hourly", {}).get("precipitation_probability", [])
    pop = pops[i] if i is not None and i < len(pops) else None

    head = f"{config.LOCATION_NAME}: {temp}C"
    if feels is not None and feels != temp:
        head += f" (feels {feels})"
    segs = [f"{head}, {cond}", f"Wind {wind} km/h {wdir}".strip()]
    if pop is not None:
        segs.append(f"Rain {pop}%")
    emoji = EMOJI.get(cur.get("weather_code"), "")
    prefix = f"{emoji} " if emoji else ""
    return prefix + ". ".join(segs) + "."


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
        temp = util.round_num(temps[j]) if j < len(temps) else "?"
        pop = pops[j] if j < len(pops) else "?"
        pts.append(f"{_hhmm(times[j])} {temp}C {pop}%")
    return f"\U0001F550 {config.LOCATION_NAME} 24h (temp/rain): " + " | ".join(pts)
