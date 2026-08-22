"""Toronto Blue Jays data via the public MLB Stats API (statsapi.mlb.com).

Free, no key. Quick commands read the schedule; detailed commands read the
live game feed (linescore, scoring plays, boxscore, pitching decisions) for
the game in progress or the most recently completed game. NEXT adds both
teams' probable starters with season W-L and ERA. All times are Eastern.
"""
import logging
from datetime import timedelta

import requests

import config
import util
from cache import cache

log = logging.getLogger(__name__)

BASE = "https://statsapi.mlb.com/api"
SCHEDULE_TTL = 60
FEED_TTL = 30
STANDINGS_TTL = 900
PITCHER_TTL = 3600
_HEADERS = {"User-Agent": config.USER_AGENT}

EVENT_SHORT = {
    "Home Run": "HR", "Single": "single", "Double": "double", "Triple": "triple",
    "Walk": "BB", "Intent Walk": "IBB", "Hit By Pitch": "HBP",
    "Sac Fly": "SF", "Sac Fly Double Play": "SF", "Sac Bunt": "SAC",
    "Grounded Into DP": "GIDP", "Double Play": "DP", "Field Error": "error",
    "Fielders Choice": "FC", "Fielders Choice Out": "FC", "Forceout": "force",
    "Wild Pitch": "WP", "Passed Ball": "PB", "Balk": "balk",
    "Groundout": "groundout", "Flyout": "flyout", "Lineout": "lineout",
    "Pop Out": "popout", "Strikeout": "K",
}


# --------------------------------------------------------------------------
# HTTP + schedule
# --------------------------------------------------------------------------
def _get(url, params=None, ttl=0, cache_key=None):
    if cache_key:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    resp = requests.get(url, params=params, headers=_HEADERS,
                        timeout=config.HTTP_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if cache_key and ttl:
        cache.set(cache_key, data, ttl)
    return data


def _schedule_games():
    today = util.now_et().date()
    params = {
        "sportId": 1,
        "teamId": config.BLUE_JAYS_ID,
        "startDate": (today - timedelta(days=14)).isoformat(),
        "endDate": (today + timedelta(days=14)).isoformat(),
        "hydrate": "team,linescore,probablePitcher",
    }
    data = _get(f"{BASE}/v1/schedule", params=params, ttl=SCHEDULE_TTL,
                cache_key="schedule")
    games = []
    for block in data.get("dates", []):
        games.extend(block.get("games", []))
    games.sort(key=lambda g: g.get("gameDate", ""))
    return games


def _feed(game_pk):
    return _get(f"{BASE}/v1.1/game/{game_pk}/feed/live", ttl=FEED_TTL,
                cache_key=f"feed:{game_pk}")


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _state(game):
    s = game.get("status", {})
    return s.get("abstractGameState", ""), s.get("detailedState", "")


def _is_live(game):
    return _state(game)[0] == "Live"


def _is_final(game):
    return _state(game)[0] == "Final"


def _abbr(team):
    return team.get("abbreviation") or team.get("teamName") or team.get("name", "?")


def _short(team):
    return team.get("teamName") or team.get("name", "?")


def _jays_side_schedule(game):
    away = game.get("teams", {}).get("away", {}).get("team", {})
    return "away" if away.get("id") == config.BLUE_JAYS_ID else "home"


def _game_date_et(game):
    dt = util.parse_utc(game.get("gameDate"))
    return util.to_et(dt).date() if dt else None


def _ordinal(n):
    if n is None:
        return ""
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _lastname(full):
    if not full:
        return ""
    parts = full.split()
    while len(parts) > 1 and parts[-1].lower().strip(".") in {"jr", "sr", "ii", "iii", "iv", "v"}:
        parts.pop()
    return parts[-1]


def _pitcher_season(pid):
    """Season W-L and ERA for a pitcher id (for probable starters)."""
    if not pid:
        return None
    try:
        season = util.now_et().year
        data = _get(f"{BASE}/v1/people/{pid}",
                    params={"hydrate": f"stats(group=[pitching],type=[season],season={season})"},
                    ttl=PITCHER_TTL, cache_key=f"pit:{pid}:{season}")
        person = (data.get("people") or [{}])[0]
        for grp in person.get("stats", []):
            for split in grp.get("splits", []):
                st = split.get("stat", {})
                if "era" in st:
                    return {"name": person.get("fullName", ""),
                            "era": st.get("era"), "w": st.get("wins"), "l": st.get("losses")}
        return {"name": person.get("fullName", ""), "era": None, "w": None, "l": None}
    except Exception as exc:
        log.warning("pitcher season stats failed for %s: %s", pid, exc)
        return None


# --------------------------------------------------------------------------
# Quick commands (schedule)
# --------------------------------------------------------------------------
def _fmt_live_short(game):
    ls = game.get("linescore", {})
    away, home = game["teams"]["away"], game["teams"]["home"]
    a_ab, h_ab = _abbr(away["team"]), _abbr(home["team"])
    a_sc, h_sc = away.get("score", 0) or 0, home.get("score", 0) or 0
    half = ls.get("inningState", "")
    inn = ls.get("currentInningOrdinal") or _ordinal(ls.get("currentInning"))
    state = f"{half} {inn}".strip()
    outs = ls.get("outs")
    if outs is not None and half in ("Top", "Bottom"):
        state += f", {outs} out"
    tail = f" - {state}" if state else ""
    return f"{a_ab} {a_sc} @ {h_ab} {h_sc}{tail}"


def _fmt_final(game, label="Final"):
    side = _jays_side_schedule(game)
    away, home = game["teams"]["away"], game["teams"]["home"]
    a_ab, h_ab = _abbr(away["team"]), _abbr(home["team"])
    a_sc, h_sc = away.get("score", 0) or 0, home.get("score", 0) or 0
    jays_sc, opp_sc = (a_sc, h_sc) if side == "away" else (h_sc, a_sc)
    result = "W" if jays_sc > opp_sc else "L" if jays_sc < opp_sc else "T"
    day = util.fmt_day_et(util.parse_utc(game.get("gameDate")))
    return f"{label} {result}: {a_ab} {a_sc}, {h_ab} {h_sc} ({day})"


def _probable_line(abbr, pp):
    if not pp or not pp.get("id"):
        return f"{abbr}: TBD"
    s = _pitcher_season(pp.get("id"))
    name = _lastname(pp.get("fullName", "") or (s or {}).get("name", ""))
    if s and s.get("era") is not None:
        return f"{abbr}: {name} ({s.get('w')}-{s.get('l')}, {s.get('era')} ERA)"
    return f"{abbr}: {name or 'TBD'}"


def _fmt_upcoming(game, prefix="Next", probables=False):
    side = _jays_side_schedule(game)
    opp = game["teams"]["home" if side == "away" else "away"]["team"]
    vs = "@" if side == "away" else "vs"
    dt = util.parse_utc(game.get("gameDate"))
    venue = game.get("venue", {}).get("name", "")
    _, detailed = _state(game)
    note = f" [{detailed}]" if detailed in ("Postponed", "Suspended") else ""
    loc = f" ({venue})" if venue else ""
    head = (f"{prefix}: TOR {vs} {_short(opp)}, "
            f"{util.fmt_day_et(dt)} {util.fmt_time_et(dt)}{loc}{note}")
    if not probables:
        return head
    away_ab = _abbr(game["teams"]["away"]["team"])
    home_ab = _abbr(game["teams"]["home"]["team"])
    lines = [head,
             _probable_line(away_ab, game["teams"]["away"].get("probablePitcher")),
             _probable_line(home_ab, game["teams"]["home"].get("probablePitcher"))]
    return "\n".join(lines)


def jays_now():
    games = _schedule_games()
    today = util.now_et().date()
    todays = [g for g in games if _game_date_et(g) == today]
    for g in todays:
        if _is_live(g):
            return _fmt_live_short(g)
    finals = [g for g in todays if _is_final(g)]
    if finals:
        return _fmt_final(finals[-1])
    upcoming = [g for g in todays if not _is_final(g) and not _is_live(g)]
    if upcoming:
        return _fmt_upcoming(upcoming[0], prefix="Today")
    return jays_next()


def jays_next():
    games = _schedule_games()
    now = util.now_et()
    for g in games:
        abstract, detailed = _state(g)
        dt = util.parse_utc(g.get("gameDate"))
        if detailed in ("Postponed", "Cancelled"):
            continue
        if abstract != "Final" and dt and dt > now:
            return _fmt_upcoming(g, prefix="Next", probables=True)
    return "No upcoming Jays game found."


def jays_last():
    games = _schedule_games()
    finals = [g for g in games if _is_final(g)]
    if not finals:
        return "No recent completed Jays game found."
    return _fmt_final(finals[-1], label="Last")


def record():
    """RECORD - Jays W-L, division rank, games back, streak."""
    season = util.now_et().year
    data = _get(f"{BASE}/v1/standings",
                params={"leagueId": 103, "season": season,
                        "standingsTypes": "regularSeason", "hydrate": "division,team"},
                ttl=STANDINGS_TTL, cache_key="standings")
    for rec in data.get("records", []):
        for tr in rec.get("teamRecords", []):
            if tr.get("team", {}).get("id") == config.BLUE_JAYS_ID:
                w, l = tr.get("wins"), tr.get("losses")
                rank = _ordinal(tr.get("divisionRank"))
                div = rec.get("division", {}).get("nameShort") or "AL East"
                gb = tr.get("divisionGamesBack", tr.get("gamesBack", "-"))
                streak = tr.get("streak", {}).get("streakCode", "")
                parts = [f"TOR {w}-{l}"]
                if rank:
                    parts.append(f"{rank} {div}")
                parts.append("1st place" if gb in ("-", "0.0", 0) else f"{gb} GB")
                if streak:
                    parts.append(streak)
                return " | ".join(parts)
    return "Jays standings unavailable right now."


# --------------------------------------------------------------------------
# Detailed commands (live feed)
# --------------------------------------------------------------------------
def _target_game():
    games = _schedule_games()
    live = next((g for g in games if _is_live(g)), None)
    if live:
        return live
    finals = [g for g in games if _is_final(g)]
    return finals[-1] if finals else None


def _feed_teams(feed):
    gd = feed.get("gameData", {}).get("teams", {})
    away, home = gd.get("away", {}), gd.get("home", {})
    jays_side = "away" if away.get("id") == config.BLUE_JAYS_ID else "home"
    return away, home, jays_side


def _state_str(feed):
    status = feed.get("gameData", {}).get("status", {}).get("abstractGameState", "")
    if status == "Final":
        return "Final"
    ls = feed.get("liveData", {}).get("linescore", {})
    return f"{ls.get('inningState', '')} {ls.get('currentInningOrdinal', '')}".strip() or "Scheduled"


def _score_line(feed):
    away, home, _ = _feed_teams(feed)
    ls = feed.get("liveData", {}).get("linescore", {}).get("teams", {})
    a_r = ls.get("away", {}).get("runs", 0) or 0
    h_r = ls.get("home", {}).get("runs", 0) or 0
    state = _state_str(feed)
    return (f"{away.get('abbreviation', 'AWY')} {a_r} @ "
            f"{home.get('abbreviation', 'HOM')} {h_r} - {state}")


def line(feed):
    ls = feed.get("liveData", {}).get("linescore", {})
    away, home, _ = _feed_teams(feed)
    a_ab = away.get("abbreviation", "AWY")
    h_ab = home.get("abbreviation", "HOM")
    a_cells, h_cells = [], []
    for inn in ls.get("innings", []):
        a = inn.get("away", {}).get("runs")
        h = inn.get("home", {}).get("runs")
        a_cells.append(str(a) if a is not None else "-")
        h_cells.append(str(h) if h is not None else "-")
    teams = ls.get("teams", {})

    def tot(side, key):
        return teams.get(side, {}).get(key, 0) or 0

    a_line = (f"{a_ab} " + " ".join(a_cells) +
              f" = {tot('away', 'runs')}R {tot('away', 'hits')}H {tot('away', 'errors')}E")
    h_line = (f"{h_ab} " + " ".join(h_cells) +
              f" = {tot('home', 'runs')}R {tot('home', 'hits')}H {tot('home', 'errors')}E")
    return f"Line ({_state_str(feed)}):\n{a_line}\n{h_line}"


def scoring(feed):
    plays = feed.get("liveData", {}).get("plays", {})
    all_plays = plays.get("allPlays", [])
    out = []
    for i in plays.get("scoringPlays", []):
        if i >= len(all_plays):
            continue
        play = all_plays[i]
        about, result = play.get("about", {}), play.get("result", {})
        half = "T" if about.get("halfInning") == "top" else "B"
        inning = about.get("inning", "")
        batter = play.get("matchup", {}).get("batter", {}).get("fullName", "")
        event = result.get("event", "")
        event_s = EVENT_SHORT.get(event, event)
        rbi = result.get("rbi", 0) or 0
        rbi_s = f" {rbi}R" if rbi else ""
        a_s, h_s = result.get("awayScore"), result.get("homeScore")
        score = f" ({a_s}-{h_s})" if a_s is not None and h_s is not None else ""
        out.append(f"{half}{inning} {_lastname(batter)} {event_s}{rbi_s}{score}".strip())
    if not out:
        return "No runs have scored."
    return "Scoring:\n" + "\n".join(out)


def batting(feed):
    """BATTING - full lineup: everyone who has batted (hits/AB, plus BB/HR/RBI)."""
    box = feed.get("liveData", {}).get("boxscore", {}).get("teams", {})
    _, _, jays_side = _feed_teams(feed)
    side = box.get(jays_side, {})
    players = side.get("players", {})
    out = []
    for pid in side.get("batters", []):
        p = players.get(f"ID{pid}", {})
        bat = p.get("stats", {}).get("batting", {})
        ab = bat.get("atBats", 0) or 0
        h = bat.get("hits", 0) or 0
        bb = bat.get("baseOnBalls", 0) or 0
        hbp = bat.get("hitByPitch", 0) or 0
        hr = bat.get("homeRuns", 0) or 0
        rbi = bat.get("rbi", 0) or 0
        pa = bat.get("plateAppearances")
        if pa is None:
            pa = ab + bb + hbp + (bat.get("sacFlies", 0) or 0) + (bat.get("sacBunts", 0) or 0)
        if pa < 1:
            continue  # in the order but hasn't come to the plate yet
        name = _lastname(p.get("person", {}).get("fullName", ""))
        extra = []
        if hr:
            extra.append(f"{hr}HR")
        if rbi:
            extra.append(f"{rbi}RBI")
        if bb:
            extra.append(f"{bb}BB")
        tail = (", " + ", ".join(extra)) if extra else ""
        out.append(f"{name} {h}-{ab}{tail}")
    if not out:
        return "No Jays batters yet."
    return "TOR batting:\n" + "\n".join(out)


def _pitcher_inning_ranges(feed):
    ranges = {}
    for play in feed.get("liveData", {}).get("plays", {}).get("allPlays", []):
        pid = play.get("matchup", {}).get("pitcher", {}).get("id")
        inn = play.get("about", {}).get("inning")
        if pid is None or inn is None:
            continue
        lo, hi = ranges.get(pid, (inn, inn))
        ranges[pid] = (min(lo, inn), max(hi, inn))
    return {pid: (str(lo) if lo == hi else f"{lo}-{hi}") for pid, (lo, hi) in ranges.items()}


def _decisions(feed):
    dec = feed.get("liveData", {}).get("decisions", {})

    def gid(key):
        return (dec.get(key) or {}).get("id")

    return {gid("winner"): "W", gid("loser"): "L", gid("save"): "SV"}


def _pitching_lines(feed, side_key, ranges, decisions):
    box = feed.get("liveData", {}).get("boxscore", {}).get("teams", {})
    side = box.get(side_key, {})
    players = side.get("players", {})
    out = []
    for pid in side.get("pitchers", []):
        p = players.get(f"ID{pid}", {})
        name = _lastname(p.get("person", {}).get("fullName", ""))
        pit = p.get("stats", {}).get("pitching", {})
        ip = pit.get("inningsPitched", "0.0")
        er = pit.get("earnedRuns", 0)
        hits = pit.get("hits", 0)
        k = pit.get("strikeOuts", 0)
        pitches = pit.get("pitchesThrown", pit.get("numberOfPitches"))
        pitch_s = f" {pitches}P" if pitches else ""
        decision = decisions.get(pid, "")
        dec_s = f" {decision}" if decision else ""
        rng = ranges.get(pid)
        rng_s = f" (inn {rng})" if rng else ""
        out.append(f"{name} {ip}IP {er}ER {hits}H {k}K{pitch_s}{dec_s}{rng_s}")
    return out


def pitching(feed):
    """PITCHING - both teams' pitchers: IP, ER, H, K, pitch count, W/L/SV, innings."""
    ranges = _pitcher_inning_ranges(feed)
    decisions = _decisions(feed)
    away, home, jays_side = _feed_teams(feed)
    opp_side = "home" if jays_side == "away" else "away"
    jays_ab = (away if jays_side == "away" else home).get("abbreviation", "TOR")
    opp_ab = (home if jays_side == "away" else away).get("abbreviation", "OPP")
    jays_lines = _pitching_lines(feed, jays_side, ranges, decisions)
    opp_lines = _pitching_lines(feed, opp_side, ranges, decisions)
    if not jays_lines and not opp_lines:
        return "No pitching data yet."
    blocks = [f"{jays_ab} pitching:\n" + ("\n".join(jays_lines) if jays_lines else "none yet"),
              f"{opp_ab} pitching:\n" + ("\n".join(opp_lines) if opp_lines else "none yet")]
    return "\n\n".join(blocks)


def bases(feed):
    """BASES - who's on base right now (live game only)."""
    if feed.get("gameData", {}).get("status", {}).get("abstractGameState") != "Live":
        return "No Jays game in progress."
    ls = feed.get("liveData", {}).get("linescore", {})
    off = ls.get("offense", {})

    def runner(key):
        return _lastname(off.get(key, {}).get("fullName", "")) or "empty"

    half = ls.get("inningState", "")
    inn = ls.get("currentInningOrdinal", "")
    outs = ls.get("outs")
    header = f"Bases ({half} {inn}".strip()
    if outs is not None:
        header += f", {outs} out"
    header += "):"
    lines = [header, f"1B: {runner('first')}", f"2B: {runner('second')}", f"3B: {runner('third')}"]
    batter = off.get("batter", {}).get("fullName")
    if batter:
        lines.append(f"AB: {_lastname(batter)}")
    return "\n".join(lines)


def full(feed):
    return "\n\n".join([
        _score_line(feed),
        line(feed),
        scoring(feed),
        batting(feed),
        pitching(feed),
    ])


def _detail(formatter, empty="No recent Jays game found."):
    game = _target_game()
    if not game:
        return empty
    return formatter(_feed(game["gamePk"]))


def cmd_line():
    return _detail(line)


def cmd_scoring():
    return _detail(scoring)


def cmd_batting():
    return _detail(batting)


def cmd_pitching():
    return _detail(pitching)


def cmd_bases():
    return _detail(bases)


def cmd_full():
    return _detail(full)
