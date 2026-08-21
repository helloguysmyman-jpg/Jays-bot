"""Combined SMS router: Killarney weather + Toronto Blue Jays.

Weather (Open-Meteo + Environment Canada): NOW, HOURLY, TODAY, FORECAST, ALERTS
Jays (MLB Stats API): SCORE, LINE, SCORING, PITCH, BATTING, FULL, NEXT, LAST, RECORD

Commands are case-insensitive and whitespace-tolerant. There are no name
clashes between the two sets, so no prefix is needed - but an optional
WX or JAYS prefix is accepted too (e.g. "WX NOW", "JAYS SCORE").
"""
import logging

import mlb
import openmeteo
import eccc

log = logging.getLogger(__name__)

MENU_TEXT = (
    "\u26C5 WEATHER (Killarney):\n"
    "NOW, HOURLY, TODAY, FORECAST, ALERTS\n"
    "\u26BE JAYS:\n"
    "SCORE, LINE, SCORING, PITCH, BATTING, FULL, NEXT, LAST, RECORD\n"
    "Reply MENU anytime."
)


def _safe(fn, err):
    try:
        return fn()
    except Exception as exc:
        log.exception("handler failed: %s", exc)
        return err


# command keyword -> (handler, error message)
WEATHER = {
    "NOW": (openmeteo.current_weather, "Weather unavailable right now."),
    "WEATHER": (openmeteo.current_weather, "Weather unavailable right now."),
    "HOURLY": (openmeteo.hourly_24, "Hourly forecast unavailable right now."),
    "24H": (openmeteo.hourly_24, "Hourly forecast unavailable right now."),
    "TODAY": (eccc.today, "Forecast unavailable right now."),
    "TONIGHT": (eccc.today, "Forecast unavailable right now."),
    "FORECAST": (eccc.forecast, "Forecast unavailable right now."),
    "3DAY": (eccc.forecast, "Forecast unavailable right now."),
    "ALERTS": (eccc.alerts, "Alerts unavailable right now."),
    "WARNINGS": (eccc.alerts, "Alerts unavailable right now."),
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
    # optional namespace prefixes
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

    if table is not None:
        entry = table.get(cmd)
        if entry:
            return _safe(*entry)
        return f"Unknown command '{cmd}'. Reply MENU for the list."

    entry = WEATHER.get(cmd) or JAYS.get(cmd)
    if entry:
        return _safe(*entry)
    return f"Unknown command '{cmd}'. Reply MENU for the list."
