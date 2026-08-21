"""Offline tests + sample-output demo for the combined bot (no network)."""
import os
import sys
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mlb
import openmeteo
import eccc
import router
import util
from cache import cache

TODAY = util.now_et().date().isoformat()


def _clear():
    cache._data.clear()


# ==========================================================================
# MLB fixtures
# ==========================================================================
FINAL_SCHED = {
    "gamePk": 900, "gameDate": f"{TODAY}T17:07:00Z",
    "status": {"abstractGameState": "Final", "detailedState": "Final"},
    "teams": {
        "away": {"score": 5, "team": {"id": 141, "abbreviation": "TOR", "teamName": "Blue Jays"}},
        "home": {"score": 1, "team": {"id": 139, "abbreviation": "TB", "teamName": "Rays"}},
    },
    "venue": {"name": "Tropicana Field"}, "linescore": {},
}
NEXT_SCHED = {
    "gamePk": 901, "gameDate": "2099-08-22T23:05:00Z",
    "status": {"abstractGameState": "Preview", "detailedState": "Scheduled"},
    "teams": {
        "away": {"team": {"id": 141, "abbreviation": "TOR", "teamName": "Blue Jays"},
                 "probablePitcher": {"id": 500, "fullName": "Kevin Gausman"}},
        "home": {"team": {"id": 147, "abbreviation": "NYY", "teamName": "Yankees"},
                 "probablePitcher": {"id": 501, "fullName": "Gerrit Cole"}},
    },
    "venue": {"name": "Yankee Stadium"},
}


def _p(inning, half, event, rbi, a, h, batter, pid):
    return {"about": {"inning": inning, "halfInning": half},
            "result": {"event": event, "rbi": rbi, "awayScore": a, "homeScore": h},
            "matchup": {"batter": {"fullName": batter}, "pitcher": {"id": pid}}}


def _bat(h, ab, hr, rbi, name):
    return {"person": {"fullName": name},
            "stats": {"batting": {"hits": h, "atBats": ab, "homeRuns": hr, "rbi": rbi}}}


def _pit(name, ip, er, hits, k):
    return {"person": {"fullName": name},
            "stats": {"pitching": {"inningsPitched": ip, "earnedRuns": er,
                                   "hits": hits, "strikeOuts": k}}}


FEED = {
    "gameData": {
        "teams": {"away": {"id": 141, "abbreviation": "TOR"},
                  "home": {"id": 139, "abbreviation": "TB"}},
        "status": {"abstractGameState": "Final"},
    },
    "liveData": {
        "decisions": {"winner": {"id": 600}, "loser": {"id": 700}, "save": {"id": 602}},
        "linescore": {
            "innings": [
                {"away": {"runs": 0}, "home": {"runs": 0}},
                {"away": {"runs": 1}, "home": {"runs": 0}},
                {"away": {"runs": 0}, "home": {"runs": 0}},
                {"away": {"runs": 0}, "home": {"runs": 1}},
                {"away": {"runs": 2}, "home": {"runs": 0}},
                {"away": {"runs": 0}, "home": {"runs": 0}},
                {"away": {"runs": 2}, "home": {"runs": 0}},
                {"away": {"runs": 0}, "home": {"runs": 0}},
                {"away": {"runs": 0}, "home": {"runs": 0}},
            ],
            "teams": {"away": {"runs": 5, "hits": 12, "errors": 1},
                      "home": {"runs": 1, "hits": 5, "errors": 1}},
        },
        "plays": {
            "scoringPlays": [0, 1, 2, 3, 4],
            "allPlays": [
                _p(2, "top", "Home Run", 1, 1, 0, "Ryan Okamoto", 700),
                _p(4, "bottom", "Single", 1, 1, 1, "Junior Caminero", 600),
                _p(5, "top", "Home Run", 1, 2, 1, "Nathan Lukes", 700),
                _p(5, "top", "Home Run", 1, 3, 1, "Daz Cameron", 700),
                _p(7, "top", "Single", 2, 5, 1, "George Springer", 701),
                _p(1, "bottom", "Groundout", 0, 0, 0, "x", 600),
                _p(7, "bottom", "Flyout", 0, 0, 0, "x", 600),
                _p(8, "bottom", "Groundout", 0, 0, 0, "x", 601),
                _p(9, "bottom", "Strikeout", 0, 0, 0, "x", 602),
            ],
        },
        "boxscore": {
            "teams": {
                "away": {
                    "batters": [10, 11, 12, 13, 14, 15],
                    "pitchers": [600, 601, 602],
                    "players": {
                        "ID10": _bat(1, 4, 0, 2, "George Springer"),
                        "ID11": _bat(2, 4, 1, 1, "Vladimir Guerrero Jr."),
                        "ID12": _bat(1, 4, 0, 0, "Bo Bichette"),
                        "ID13": _bat(1, 3, 1, 1, "Ryan Okamoto"),
                        "ID14": _bat(1, 4, 1, 1, "Nathan Lukes"),
                        "ID15": _bat(1, 4, 1, 1, "Daz Cameron"),
                        "ID600": _pit("Shane Bieber", "7.0", 1, 4, 7),
                        "ID601": _pit("Mason Miles", "1.0", 0, 0, 0),
                        "ID602": _pit("Louis Varland", "1.0", 0, 1, 1),
                    },
                },
                "home": {"batters": [], "pitchers": [700, 701], "players": {}},
            }
        },
    },
}

STANDINGS = {
    "records": [{
        "division": {"nameShort": "AL East"},
        "teamRecords": [{
            "team": {"id": 141}, "wins": 78, "losses": 60,
            "divisionRank": "2", "divisionGamesBack": "3.0",
            "streak": {"streakCode": "W2"},
        }],
    }]
}


def _pitcher_people(pid):
    stats = {500: (3.45, 12, 9, "Kevin Gausman"), 501: (2.98, 14, 5, "Gerrit Cole")}
    era, w, l, name = stats[pid]
    return {"people": [{"fullName": name,
                        "stats": [{"splits": [{"stat": {"era": era, "wins": w, "losses": l}}]}]}]}


def _fake_get(url, params=None, ttl=0, cache_key=None):
    if "/standings" in url:
        return STANDINGS
    if "/people/" in url:
        pid = int(url.rstrip("/").split("/")[-1])
        return _pitcher_people(pid)
    raise AssertionError(f"unexpected _get for {url}")


def _patch_detail(monkeypatch):
    monkeypatch.setattr(mlb, "_schedule_games", lambda: [FINAL_SCHED])
    monkeypatch.setattr(mlb, "_feed", lambda pk: FEED)


# ==========================================================================
# Weather fixtures
# ==========================================================================
_base = util.now_et().replace(minute=0, second=0, microsecond=0)
_TIMES = [(_base + timedelta(hours=k)).strftime("%Y-%m-%dT%H:00") for k in range(26)]
OPENMETEO = {
    "current": {"temperature_2m": 18.3, "apparent_temperature": 17.1, "precipitation": 0.0,
                "weather_code": 2, "wind_speed_10m": 12.4, "wind_direction_10m": 270},
    "hourly": {"time": _TIMES,
               "precipitation_probability": [15] * 26,
               "temperature_2m": [18] * 26, "weather_code": [2] * 26},
}
ECCC_DAILY = [
    {"period": "Today", "text_summary": "Chance of showers. High 22."},
    {"period": "Tonight", "text_summary": "Clearing. Low 12."},
    {"period": "Wednesday", "text_summary": "Sunny. High 24."},
]
ECCC_ALERTS = {"warnings": {"label": "Warnings",
                            "value": [{"title": "Severe Thunderstorm Warning", "date": "2:15 PM EDT"}]},
               "watches": {"label": "Watches", "value": []},
               "advisories": {"label": "Advisories", "value": []}}
ECCC_NONE = {k: {"label": k.title(), "value": []} for k in ("warnings", "watches", "advisories")}


# ==========================================================================
# Tests - Jays
# ==========================================================================
def test_pitching_saves_and_decisions(monkeypatch):
    _clear(); _patch_detail(monkeypatch)
    out = mlb.cmd_pitching()
    assert "Bieber 7.0IP 1ER 4H 7K W (inn 1-7)" in out       # winning pitcher tagged W
    assert "Varland 1.0IP 0ER 1H 1K SV (inn 9)" in out       # save tagged SV
    assert "Miles 1.0IP 0ER 0H 0K (inn 8)" in out


def test_batting(monkeypatch):
    _clear(); _patch_detail(monkeypatch)
    out = mlb.cmd_batting()
    assert "TOR batting:" in out
    assert "Guerrero 2-4, 1HR, 1RBI" in out
    assert "Springer 1-4, 2RBI" in out


def test_line(monkeypatch):
    _clear(); _patch_detail(monkeypatch)
    out = mlb.cmd_line()
    assert "TOR 0 1 0 0 2 0 2 0 0 = 5R 12H 1E" in out
    assert "TB 0 0 0 1 0 0 0 0 0 = 1R 5H 1E" in out


def test_scoring(monkeypatch):
    _clear(); _patch_detail(monkeypatch)
    out = mlb.cmd_scoring()
    assert "T2 Okamoto HR 1R (1-0)" in out
    assert "T7 Springer 1B 2R (5-1)" in out


def test_full_has_all_sections(monkeypatch):
    _clear(); _patch_detail(monkeypatch)
    out = mlb.cmd_full()
    for token in ("TOR 5 @ TB 1 - Final", "Line (Final)", "Scoring:", "TOR batting:", "TOR pitching:"):
        assert token in out


def test_last(monkeypatch):
    _clear()
    monkeypatch.setattr(mlb, "_schedule_games", lambda: [FINAL_SCHED])
    out = mlb.jays_last()
    assert "Last W: TOR 5, TB 1" in out


def test_next_with_probables(monkeypatch):
    _clear()
    monkeypatch.setattr(mlb, "_schedule_games", lambda: [NEXT_SCHED])
    monkeypatch.setattr(mlb, "_get", _fake_get)
    out = mlb.jays_next()
    assert "Next: TOR @ Yankees" in out and "Yankee Stadium" in out
    assert "TOR: Gausman (12-9, 3.45 ERA)" in out
    assert "NYY: Cole (14-5, 2.98 ERA)" in out


def test_record(monkeypatch):
    _clear()
    monkeypatch.setattr(mlb, "_get", _fake_get)
    out = mlb.record()
    assert "TOR 78-60" in out and "2nd AL East" in out and "3.0 GB" in out and "W2" in out


# ==========================================================================
# Tests - Weather
# ==========================================================================
def test_now(monkeypatch):
    _clear()
    monkeypatch.setattr(openmeteo, "_fetch", lambda: OPENMETEO)
    out = openmeteo.current_weather()
    assert "Killarney PP: 18C (feels 17)" in out and "Partly cloudy" in out


def test_alerts(monkeypatch):
    _clear()
    monkeypatch.setattr(eccc, "_fetch", lambda: {"daily": ECCC_DAILY, "alerts": ECCC_ALERTS})
    out = eccc.alerts()
    assert "WARNINGS: Severe Thunderstorm Warning - 2:15 PM EDT" in out


def test_today_alert_banner(monkeypatch):
    _clear()
    monkeypatch.setattr(eccc, "_fetch", lambda: {"daily": ECCC_DAILY, "alerts": ECCC_ALERTS})
    out = eccc.today()
    assert "ALERT WARNINGS: Severe Thunderstorm Warning" in out
    assert "Today: Chance of showers. High 22." in out


# ==========================================================================
# Tests - routing
# ==========================================================================
def test_menu(monkeypatch):
    _clear()
    m = router.handle("MENU")
    assert "WEATHER (Killarney):" in m and "JAYS:" in m
    # weather appears above jays
    assert m.index("WEATHER") < m.index("JAYS:")


def test_routing(monkeypatch):
    _clear(); _patch_detail(monkeypatch)
    monkeypatch.setattr(mlb, "_get", _fake_get)
    monkeypatch.setattr(openmeteo, "_fetch", lambda: OPENMETEO)
    monkeypatch.setattr(eccc, "_fetch", lambda: {"daily": ECCC_DAILY, "alerts": ECCC_NONE})
    assert "TOR pitching:" in router.handle("pitch")
    assert "TOR pitching:" in router.handle("jays pitch")      # JAYS prefix
    assert "Killarney PP: 18C" in router.handle("now")
    assert "Killarney PP: 18C" in router.handle("wx now")      # WX prefix
    assert "No active alerts" in router.handle("alerts")
    assert router.handle("").startswith("\u26C5 WEATHER")      # empty -> menu
    assert router.handle("banana").startswith("Unknown command 'BANANA'")


def test_error_caught(monkeypatch):
    _clear()

    def boom():
        raise RuntimeError("down")

    monkeypatch.setattr(mlb, "_schedule_games", boom)
    assert router.handle("SCORE") == "Jays data unavailable right now."


if __name__ == "__main__":
    class MP:
        def setattr(self, o, n, v): setattr(o, n, v)

    mp = MP()
    _patch_detail(mp)
    mp.setattr(mlb, "_get", _fake_get)
    mp.setattr(openmeteo, "_fetch", lambda: OPENMETEO)
    mp.setattr(eccc, "_fetch", lambda: {"daily": ECCC_DAILY, "alerts": ECCC_ALERTS})
    demos = [
        ("MENU", lambda: router.handle("MENU")),
        ("NOW", openmeteo.current_weather),
        ("ALERTS", eccc.alerts),
        ("TODAY", eccc.today),
        ("SCORE/LAST", mlb.jays_last),
        ("LINE", mlb.cmd_line),
        ("SCORING", mlb.cmd_scoring),
        ("BATTING", mlb.cmd_batting),
        ("PITCH", mlb.cmd_pitching),
        ("RECORD", mlb.record),
        ("FULL", mlb.cmd_full),
    ]
    for name, fn in demos:
        # NEXT needs the NEXT schedule; handle separately below
        s = fn()
        print(f"\n### {name}\n{s}")
    mp.setattr(mlb, "_schedule_games", lambda: [NEXT_SCHED])
    print(f"\n### NEXT\n{mlb.jays_next()}")
