# Jays SMS Bot

Text a number for Toronto Blue Jays scores and box-score detail — built for
low/no-data trips where all you have is basic texting (e.g. over satellite).
No LLM or paid AI at runtime; it calls the public MLB Stats API directly.

## Commands

| Text | Reply |
|------|-------|
| `SCORE` (or `JAYS`) | Quick line: score + inning/outs if live, else today's result or next game |
| `LINE` | Inning-by-inning runs for both teams + R/H/E totals |
| `SCORING` | Every scoring play: inning, batter, result, RBIs, running score |
| `PITCH` | Jays pitchers in order: innings pitched, earned runs, hits, K, and which innings they threw |
| `FULL` | Everything above in one message (multiple SMS segments) |
| `NEXT` | Next game: opponent, location, start time (ET) |
| `LAST` | Result of the most recently completed game |
| `HELP` | Command list |

`LINE`, `SCORING`, `PITCH`, and `FULL` report the game in progress, or the
most recently completed game if none is live — so you can pull the box score
after it ends. Commands are case-insensitive and ignore extra spaces. Replies
are GSM-7 clean; most are one segment, `FULL` runs to a few.

Sample (live game):

```
SCORE    TOR 4 @ NYY 2 - Top 7th, 1 out
LINE     Line (Top 7th):
         TOR 0 1 0 2 0 0 1 = 4R 8H 0E
         NYY 0 0 0 0 1 1 - = 2R 6H 1E
SCORING  T2 Springer HR 1R (1-0)
         T4 Guerrero 2B 2R (3-0)
         B6 Soto SF 1R (3-2)
PITCH    Gausman 6.0IP 2ER 5H 7K (inn 5-6)
```

## Data source

MLB Stats API (`statsapi.mlb.com`), free, no key. Blue Jays are team `141`.
The schedule endpoint drives quick commands; the live game feed
(`/game/{id}/feed/live`) provides the per-inning linescore, scoring plays,
and boxscore pitching lines. Data is MLB Advanced Media's, for personal use.

## Project structure

```
jays-bot/            (all files at the repo root - no subfolders)
  app.py            # Flask webhook (/sms, /health) + `test` CLI
  router.py         # parse + dispatch commands
  mlb.py            # MLB Stats API client + formatting
  config.py  cache.py  ratelimit.py  util.py
  test_bot.py       # offline tests (fixtures, no network)
  requirements.txt  Procfile  runtime.txt  .env.example  .gitignore
```

## Run and test locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # set VALIDATE_TWILIO_SIGNATURE=false for local

python app.py test "SCORE"    # prints the reply + segment count, no SMS
python app.py test "full"
python -m pytest -q           # offline suite (fixtures)
```

## Deploy (Railway) + Twilio

1. Push this folder to GitHub → Railway **New Project → Deploy from GitHub repo**
   (it reads the `Procfile`). Render/Fly work too; keep one always-on web worker.
2. Railway **Variables**: `TWILIO_AUTH_TOKEN`, `VALIDATE_TWILIO_SIGNATURE=true`,
   and `PUBLIC_URL=https://<app>.up.railway.app/sms`.
3. **Settings → Networking → Generate Domain**; check `…/health` returns `ok`.
4. Twilio: buy a **Canadian local** SMS number → number's **Messaging → "A
   message comes in" → HTTP POST → `https://<app>.up.railway.app/sms`**. Put the
   account **Auth Token** in `TWILIO_AUTH_TOKEN`. Text `HELP` to confirm.

Env vars are documented in `.env.example`. Cost: Twilio number ~US$1–2/mo +
per-text fractions of a cent; hosting ~US$5/mo; MLB API free.

## Pre-trip checklist

- [ ] `python -m pytest -q` passes; `/health` returns `ok`.
- [ ] Twilio webhook points at `…/sms` (POST); Auth Token set; signature on.
- [ ] From your phone: `SCORE`, `LINE`, `SCORING`, `PITCH`, `FULL`, `NEXT`,
      `LAST`, `HELP` all return sensible data.
- [ ] Save the number as a contact.
- [ ] Satellite test (once Rogers is active): text from a real dead zone and
      confirm a reply — the one leg that can't be tested from home.
