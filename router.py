"""Parse an incoming SMS body and dispatch to a Blue Jays handler.

Case-insensitive, whitespace-tolerant, and error-safe (an API failure
returns a short message rather than a crash).
"""
import logging

import mlb

log = logging.getLogger(__name__)

HELP_TEXT = ("Jays: SCORE, LINE, SCORING, PITCH, FULL, NEXT, LAST, HELP. "
             "SCORE=quick score; FULL=everything (multi-text).")


def _safe(fn, err):
    try:
        return fn()
    except Exception as exc:
        log.exception("handler failed: %s", exc)
        return err


def handle(body):
    text = " ".join((body or "").strip().upper().split())
    if not text:
        return HELP_TEXT
    cmd = text.split()[0]

    if cmd in ("SCORE", "JAYS"):
        return _safe(mlb.jays_now, "Jays data unavailable right now.")
    if cmd in ("LINE", "INNINGS"):
        return _safe(mlb.cmd_line, "Jays line score unavailable right now.")
    if cmd in ("SCORING", "RUNS"):
        return _safe(mlb.cmd_scoring, "Jays scoring unavailable right now.")
    if cmd in ("PITCH", "PITCHING", "ARMS"):
        return _safe(mlb.cmd_pitching, "Jays pitching unavailable right now.")
    if cmd in ("FULL", "BOX"):
        return _safe(mlb.cmd_full, "Jays box score unavailable right now.")
    if cmd == "NEXT":
        return _safe(mlb.jays_next, "Jays schedule unavailable right now.")
    if cmd == "LAST":
        return _safe(mlb.jays_last, "Jays results unavailable right now.")
    if cmd == "HELP":
        return HELP_TEXT
    return f"Unknown command '{cmd}'. " + HELP_TEXT
