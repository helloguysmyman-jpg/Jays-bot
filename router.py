"""Combined SMS router: Killarney weather + Toronto Blue Jays.

Weather (Open-Meteo + official Environment Canada alerts):
  NOW, HOURLY, TODAY, FORECAST, ALERTS
Jays (MLB Stats API):
  SCORE, LINE, SCORING, PITCH, BATTING, BASES, FULL, NEXT, LAST, RECORD
KEY explains the abbreviations.

Case-insensitive and whitespace-tolerant. No prefix needed (there are no name
clashes); an optional WX or JAYS prefix is also accepted.
"""
import logging

import mlb
import openmeteo
import eccc

log = logging.getLogger(__name__)

MENU_TEXT = (
    "WEATHER (Killarney):\n"
    "NOW, HOURLY, TODAY, FORECAST, ALERTS\n"
    "JAYS:\n"
    "SCORE, LINE, SCORING, PITCH, BATTING, BASES, FULL, NEXT, LAST, RECORD\n"
    "KEY = abbreviations. Reply MENU anytime."
)

KEY_TEXT = (
    "KEY:\n"
    "Batting: X-Y = hits-atBats. BB=walk, RBI=runs batted in, HR=home run.\n"
    "Hits: single, double, triple, HR.\n"
    "Pitching: IP=innings, ER=earned runs, H=hits, K=strikeouts, P=pitches,\n"
    "W/L/SV=win/loss/save, inn=innings worked.\n"
    "Line: R/H/E = runs/hits/errors.\n"
    "Bases: 1B/2B/3B = who's on that base, AB = batter up.\n"
    "Weather: % = rain chance, mm = rainfall."
)


def _safe(fn, err):
    try:
        return fn()
    except Exception as exc:
        log.exception("handler failed: %s", exc)
        return err


def _weather_alerts():
    """Official ECCC alerts if reachable, else the forecast-based watch."""
    try:
        official = eccc.alerts()
        if official is not None:
            return official
    except Exception as exc:
        log.warning("eccc alerts error: %s", exc)
    return openmeteo.alerts()


def _today():
    """TODAY forecast, with an official ECCC banner on top if one is active."""
    body = openmeteo.today()
    try:
        b = eccc.banner()
    except Exception:
        b = ""
    return f"{b}\n{body}" if b else body


WEATHER = {
    "NOW": (openmeteo.current_weather, "Weather unavailable right now."),
    "WEATHER": (openmeteo.current_weather, "Weather unavailable right now."),
    "HOURLY": (openmeteo.hourly_24, "Hourly forecast unavailable right now."),
    "24H": (openmeteo.hourly_24, "Hourly forecast unavailable right now."),
    "TODAY": (_today, "Forecast unavailable right now."),
    "TONIGHT": (_today, "Forecast unavailable right now."),
    "FORECAST": (openmeteo.forecast, "Forecast unavailable right now."),
    "3DAY": (openmeteo.forecast, "Forecast unavailable right now."),
    "ALERTS": (_weather_alerts, "Alerts unavailable right now."),
    "WARNINGS": (_weather_alerts, "Alerts unavailable right now."),
}
JAYS = {
    "SCORE": (mlb.jays_now, "Jays data unavailable right now."),
    "JAYS": (mlb.jays_now, "Jays data unavailable right now."),
    "LINE": (mlb.cmd_line, "Jays line score unavailable right now."),
    "INNINGS": (mlb.cmd_line, "Jays line score unavailable right now."),
    "SCORING": (mlb.cmd_scoring, "Jays scoring unavailable right now."),
    "RUNS": (mlb.cmd_scoring, "Jays scoring unavailable right now."),
    "PITCH": (mlb.cmd_pitching, "Jays pitching unavailable right now."),
    "PITCHING": (mlb.cmd_pitching, "Jays pitching unavailable right now."),
    "ARMS": (mlb.cmd_pitching, "Jays pitching unavailable right now."),
    "BATTING": (mlb.cmd_batting, "Jays batting unavailable right now."),
    "BATS": (mlb.cmd_batting, "Jays batting unavailable right now."),
    "HITTERS": (mlb.cmd_batting, "Jays batting unavailable right now."),
    "BASES": (mlb.cmd_bases, "Jays base state unavailable right now."),
    "RUNNERS": (mlb.cmd_bases, "Jays base state unavailable right now."),
    "ONBASE": (mlb.cmd_bases, "Jays base state unavailable right now."),
    "FULL": (mlb.cmd_full, "Jays box score unavailable right now."),
    "BOX": (mlb.cmd_full, "Jays box score unavailable right now."),
    "NEXT": (mlb.jays_next, "Jays schedule unavailable right now."),
    "LAST": (mlb.jays_last, "Jays results unavailable right now."),
    "RECORD": (mlb.record, "Jays standings unavailable right now."),
    "STANDINGS": (mlb.record, "Jays standings unavailable right now."),
}


def handle(body):
    tokens = " ".join((body or "").strip().upper().split()).split()
    if not tokens:
        return MENU_TEXT

    first = tokens[0]
    if first in ("WX", "WEATHER") and len(tokens) > 1:
        table, cmd = WEATHER, tokens[1]
    elif first == "JAYS" and len(tokens) > 1:
        table, cmd = JAYS, tokens[1]
    elif first == "WX":
        table, cmd = WEATHER, "NOW"
    else:
        table, cmd = None, first

    if cmd in ("MENU", "CMDS", "HELP", "COMMANDS"):
        return MENU_TEXT
    if cmd in ("KEY", "LEGEND", "GLOSSARY", "ABBR"):
        return KEY_TEXT

    if table is not None:
        entry = table.get(cmd)
        return _safe(*entry) if entry else f"Unknown command '{cmd}'. Reply MENU for the list."

    entry = WEATHER.get(cmd) or JAYS.get(cmd)
    if entry:
        return _safe(*entry)
    return f"Unknown command '{cmd}'. Reply MENU for the list."
