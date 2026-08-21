# Jays + Killarney Weather SMS Bot (combined)

One SMS bot, one phone number: Toronto Blue Jays scores/box-score detail **and**
Killarney Provincial Park weather (incl. official Environment Canada severe-weather
alerts). Built for low/no-data trips where all you have is basic texting. No LLM
at runtime.

## Commands

Text `MENU` any time for the list. No prefix needed (an optional `WX` or `JAYS`
prefix also works).

**Weather** (Open-Meteo + Environment Canada)

| Text | Reply |
|------|-------|
| `NOW` | Current temp, feels-like, conditions, wind, rain chance |
| `HOURLY` | Next 24h in 3-hour steps: time, temp, rain chance |
| `TODAY` | Environment Canada worded today + tonight (alert banner if active) |
| `FORECAST` | Environment Canada worded outlook, next ~3 days |
| `ALERTS` | Active warnings / watches / advisories |

**Jays** (MLB Stats API)

| Text | Reply |
|------|-------|
| `SCORE` | Live score/inning, else today's result or next game |
| `LINE` | Inning-by-inning runs + R/H/E |
| `SCORING` | Every scoring play: inning, batter, result, RBIs, running score |
| `PITCH` | Jays pitchers: IP, ER, H, K, **W/L/SV decision**, innings used |
| `BATTING` | Jays hitters who contributed: H-AB, HR, RBI |
| `FULL` | Everything above in one message (many segments) |
| `NEXT` | Next game + **both probable starters with W-L and ERA** |
| `LAST` | Result of the most recently completed game |
| `RECORD` | Jays W-L, division rank, games back, streak |

Commands are case-insensitive and whitespace-tolerant. `HELP`/`STOP` are carrier
keywords intercepted before they reach the bot — use `MENU` for the list.

## Data sources

- MLB Stats API (`statsapi.mlb.com`) - free, no key. Blue Jays = team 141.
- Open-Meteo (`api.open-meteo.com`) - free, no key - current + 24h hourly.
- Environment Canada via the `env_canada` library - worded day/night forecast +
  official alerts. It's the heaviest dependency (pulls in pandas/lxml/Pillow) and
  is async; the app calls it with `asyncio.run()`. **Keep the app at one gunicorn
  worker** (the Procfile does this) and don't switch to a gevent worker class.

## A note on emojis and SMS length

Replies use emojis. Any emoji forces a message into Unicode (UCS-2) encoding,
which drops the per-segment limit from 160 to 70 characters - so emoji replies
use more SMS segments (e.g. `FULL` can be ~8). At personal volume this is a few
cents and well within the free tier, but it's why long replies split into several
texts. To make the big data commands lean again, remove the emoji prefixes in
`mlb.py` (the `\U0001F...`/`\u26...` bits) from `line`, `scoring`, `batting`,
`pitching`, and the section headers.

## Deploy (Railway) + Twilio

Flat layout - every file sits at the repo root (no subfolders), so drag them all
in when uploading to GitHub.

1. Push to GitHub -> Railway **New Project -> Deploy from GitHub repo** (reads the
   `Procfile`). Keep **one** web worker.
2. Railway **Variables**: `TWILIO_AUTH_TOKEN`, `VALIDATE_TWILIO_SIGNATURE=true`,
   `PUBLIC_URL=https://<app>.up.railway.app/sms`.
3. **Settings -> Networking -> Generate Domain**; check `/health` returns `ok`.
4. Point your Twilio number's **"A message comes in"** webhook (HTTP POST) at
   `https://<app>.up.railway.app/sms`.

Reuse the same Twilio number you already have - just repoint its webhook at this
new app's URL.

## Local test

```bash
pip install -r requirements.txt        # env_canada makes this slower
python app.py test "PITCH"             # prints reply + segment count, no SMS
python app.py test "wx now"
python -m pytest -q                    # offline suite (fixtures, no network)
```

## env vars

See `.env.example`: `TWILIO_AUTH_TOKEN`, `VALIDATE_TWILIO_SIGNATURE`, `PUBLIC_URL`,
`RATE_LIMIT_PER_MIN`/`_DAY`, `HTTP_TIMEOUT`, `LOG_LEVEL`.

## Auto-alerts (not built)

Game-start / final / severe-weather push alerts were intentionally left out: they
need a 24/7 background poller, they send automated texts that consume the free SMS
tier and then cost ~1c each, and push delivery is unreliable over satellite. Add
later once normal text volume is known.
