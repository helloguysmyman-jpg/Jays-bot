"""Offline tests + sample-output demo for the Jays bot (no network)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mlb, router  # noqa: E402
import util  # noqa: E402
from cache import cache  # noqa: E402

TODAY = util.now_et().date().isoformat()


def _clear():
    cache._data.clear()


# --- schedule-shaped games (for SCORE / NEXT / LAST) ---
SCHED_LIVE = {
    "gamePk": 111, "gameDate": f"{TODAY}T23:07:00Z",
    "status": {"abstractGameState": "Live", "detailedState": "In Progress"},
    "teams": {
        "away": {"score": 4, "team": {"id": 141, "abbreviation": "TOR", "teamName": "Blue Jays"}},
        "home": {"score": 2, "team": {"id": 147, "abbreviation": "NYY", "teamName": "Yankees"}},
    },
    "venue": {"name": "Yankee Stadium"},
    "linescore": {"currentInning": 7, "currentInningOrdinal": "7th", "inningState": "Top", "outs": 1},
}
SCHED_FINAL = {
    "gamePk": 112, "gameDate": f"{TODAY}T17:07:00Z",
    "status": {"abstractGameState": "Final", "detailedState": "Final"},
    "teams": {
        "away": {"score": 5, "team": {"id": 141, "abbreviation": "TOR", "teamName": "Blue Jays"}},
        "home": {"score": 3, "team": {"id": 111, "abbreviation": "BOS", "teamName": "Red Sox"}},
    },
    "venue": {"name": "Fenway Park"}, "linescore": {},
}
SCHED_NEXT = {
    "gamePk": 113, "gameDate": "2099-08-22T23:10:00Z",
    "status": {"abstractGameState": "Preview", "detailedState": "Scheduled"},
    "teams": {
        "away": {"team": {"id": 141, "abbreviation": "TOR", "teamName": "Blue Jays"}},
        "home": {"team": {"id": 111, "abbreviation": "BOS", "teamName": "Red Sox"}},
    },
    "venue": {"name": "Fenway Park"}, "linescore": {},
}

# --- live feed fixture (for LINE / SCORING / PITCH / FULL) ---
def _p(inning, half, event, rbi, a, h, batter, pid):
    return {"about": {"inning": inning, "halfInning": half},
            "result": {"event": event, "rbi": rbi, "awayScore": a, "homeScore": h},
            "matchup": {"batter": {"fullName": batter}, "pitcher": {"id": pid}}}


FEED = {
    "gameData": {
        "teams": {"away": {"id": 141, "abbreviation": "TOR", "teamName": "Blue Jays"},
                  "home": {"id": 147, "abbreviation": "NYY", "teamName": "Yankees"}},
        "status": {"abstractGameState": "Live"},
    },
    "liveData": {
        "linescore": {
            "inningState": "Top", "currentInningOrdinal": "7th", "currentInning": 7, "outs": 1,
            "innings": [
                {"away": {"runs": 0}, "home": {"runs": 0}},
                {"away": {"runs": 1}, "home": {"runs": 0}},
                {"away": {"runs": 0}, "home": {"runs": 0}},
                {"away": {"runs": 2}, "home": {"runs": 0}},
                {"away": {"runs": 0}, "home": {"runs": 1}},
                {"away": {"runs": 0}, "home": {"runs": 1}},
                {"away": {"runs": 1}, "home": {"runs": None}},
            ],
            "teams": {"away": {"runs": 4, "hits": 8, "errors": 0},
                      "home": {"runs": 2, "hits": 6, "errors": 1}},
        },
        "plays": {
            "scoringPlays": [0, 1, 2, 3],
            "allPlays": [
                _p(2, "top", "Home Run", 1, 1, 0, "George Springer", 500),
                _p(4, "top", "Double", 2, 3, 0, "Vladimir Guerrero Jr.", 500),
                _p(5, "bottom", "Single", 1, 3, 1, "Aaron Judge", 600),
                _p(6, "bottom", "Sac Fly", 1, 3, 2, "Juan Soto", 600),
            ],
        },
        "boxscore": {
            "teams": {
                "away": {  # Blue Jays
                    "pitchers": [600],
                    "players": {"ID600": {"person": {"fullName": "Kevin Gausman"},
                                          "stats": {"pitching": {"inningsPitched": "6.0",
                                                                 "earnedRuns": 2, "hits": 5,
                                                                 "strikeOuts": 7}}}},
                },
                "home": {"pitchers": [500], "players": {}},
            }
        },
    },
}


def _patch_detail(monkeypatch):
    monkeypatch.setattr(mlb, "_schedule_games", lambda: [SCHED_LIVE])
    monkeypatch.setattr(mlb, "_feed", lambda pk: FEED)


# --------------------------------------------------------------------------
def test_score(monkeypatch):
    _clear()
    monkeypatch.setattr(mlb, "_schedule_games", lambda: [SCHED_LIVE])
    out = mlb.jays_now()
    assert out == "TOR 4 @ NYY 2 - Top 7th, 1 out"


def test_next(monkeypatch):
    _clear()
    monkeypatch.setattr(mlb, "_schedule_games", lambda: [SCHED_NEXT])
    out = mlb.jays_next()
    assert out.startswith("Next: TOR @ Red Sox") and "Fenway Park" in out


def test_last(monkeypatch):
    _clear()
    monkeypatch.setattr(mlb, "_schedule_games", lambda: [SCHED_FINAL])
    out = mlb.jays_last()
    assert out.startswith("Last W:") and "TOR 5" in out


def test_line(monkeypatch):
    _clear()
    _patch_detail(monkeypatch)
    out = mlb.cmd_line()
    assert "Line (Top 7th):" in out
    assert "TOR 0 1 0 2 0 0 1 = 4R 8H 0E" in out
    assert "NYY 0 0 0 0 1 1 - = 2R 6H 1E" in out


def test_scoring(monkeypatch):
    _clear()
    _patch_detail(monkeypatch)
    out = mlb.cmd_scoring()
    assert "T2 Springer HR 1R (1-0)" in out
    assert "T4 Guerrero 2B 2R (3-0)" in out
    assert "B6 Soto SF 1R (3-2)" in out


def test_pitching(monkeypatch):
    _clear()
    _patch_detail(monkeypatch)
    out = mlb.cmd_pitching()
    assert "TOR pitching:" in out
    assert "Gausman 6.0IP 2ER 5H 7K" in out and "inn 5-6" in out


def test_full(monkeypatch):
    _clear()
    _patch_detail(monkeypatch)
    out = mlb.cmd_full()
    for token in ("TOR 4 @ NYY 2 - Top 7th", "Line (", "Scoring:", "TOR pitching:"):
        assert token in out


def test_router(monkeypatch):
    _clear()
    _patch_detail(monkeypatch)
    assert "TOR pitching:" in router.handle("  full ")
    assert router.handle("help").startswith("Jays:")
    assert router.handle("").startswith("Jays:")
    assert router.handle("frisbee").startswith("Unknown command 'FRISBEE'")


def test_error_caught(monkeypatch):
    _clear()

    def boom():
        raise RuntimeError("API down")

    monkeypatch.setattr(mlb, "_schedule_games", boom)
    assert router.handle("SCORE") == "Jays data unavailable right now."


if __name__ == "__main__":
    class MP:
        def setattr(self, o, n, v): setattr(o, n, v)

    mp = MP()
    _patch_detail(mp)
    demos = [
        ("SCORE", mlb.jays_now), ("LINE", mlb.cmd_line), ("SCORING", mlb.cmd_scoring),
        ("PITCH", mlb.cmd_pitching), ("FULL", mlb.cmd_full),
    ]
    for name, fn in demos:
        s = fn()
        print(f"\n### {name}\n{s}\n[{len(s)} chars]")
