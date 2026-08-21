# Jays + Killarney Weather SMS Bot (combined)

One SMS bot, one phone number: Toronto Blue Jays scores/box-score detail **and**
Killarney Provincial Park weather. Built for low/no-data trips where all you have
is basic texting. No LLM at runtime, and no heavy dependencies - it calls the MLB
Stats API and Open-Meteo directly.

## Commands

Text `MENU` for the list. No prefix needed (optional `WX`/`JAYS` prefix also works).

**Weather** (Open-Meteo): `NOW`, `HOURLY`, `TODAY`, `FORECAST`, `ALERTS`
**Jays** (MLB Stats API): `SCORE`, `LINE`, `SCORING`, `PITCH`, `BATTING`, `FULL`, `NEXT`, `LAST`, `RECORD`

- `PITCH` tags the winning/losing pitcher and save (`W`/`L`/`SV`).
- `NEXT` shows both probable starters with season W-L and ERA.
- `RECORD` = Jays W-L, division rank, games back, streak.
- `HELP`/`STOP` are carrier keywords intercepted before the bot - use `MENU`.

## Data sources

- MLB Stats API (`statsapi.mlb.com`) - free, no key. Blue Jays = team 141.
- Open-Meteo (`api.open-meteo.com`) - free, no key - all weather.

**ALERTS is forecast-based, not official.** Open-Meteo does not carry official
government warnings, so `ALERTS` derives a severe-weather watch from the forecast
(thunder, heavy precip, strong wind, freezing in the next 24h) and says so. For
official Environment Canada warnings/watches, check weather.gc.ca. (An official
ECCC source can be added later via a lightweight endpoint.)

## Deploy (Railway) + Twilio

Flat layout - every file sits at the repo root (no subfolders).

1. Push to GitHub -> Railway **Deploy from GitHub repo** (reads `Procfile`). One worker.
2. Variables: `TWILIO_AUTH_TOKEN`, `VALIDATE_TWILIO_SIGNATURE=true`,
   `PUBLIC_URL=https://<app>.up.railway.app/sms`.
3. **Generate Domain**; check `/health` returns `ok`.
4. Point the Twilio number's **"A message comes in"** webhook (HTTP POST) at
   `https://<app>.up.railway.app/sms`. Reuse your existing number - just repoint it.

## Local test

```bash
pip install -r requirements.txt
python app.py test "PITCH"     # prints reply + segment count, no SMS
python app.py test "wx now"
python -m pytest -q            # offline suite (fixtures, no network)
```

## Auto-alerts (not built)

Game-start / final / severe-weather push alerts were left out on purpose: they need
a 24/7 poller, they send automated texts that consume the free SMS tier and then
cost ~1c each, and push delivery is unreliable over satellite. Add later once
normal text volume is known.
