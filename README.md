# 📡 Market Radar
Business, startup and market-sentiment briefing (India first, global second). Runs free on GitHub Actions; nothing depends on your laptop.

**Schedule (IST):** 07:30, 13:00, 19:00 daily · Sunday 10:00 weekly digest.
**Flow:** fetch RSS → dedupe → Gemini scores 0–10 (keep ≥7) → Gemini writes strict-JSON cards (validated, retried once) → verify → dashboard + email + phone push.

## Rules baked in
- **Big Move** needs an *Official* source OR 2+ outlets; otherwise it's downgraded to Notable with an "Unconfirmed" chip.
- The big number must literally appear in the source text, else it's replaced by "-" and the card is marked Unconfirmed.
- Official items (RBI/SEBI/PIB/exchange) → original saved to `docs/archive/YYYY/MM/`. News → summary + link only.
- Nothing scores ≥7 and new → **no email, no push**.
- Source failing 3 runs in a row → shown in the dashboard health strip.

## Data sources (all free, no API keys)
- News/official: RSS feeds in `config/sources.yaml` (checked live 2026-10-19; dead ones are listed under `dead:`).
- **Market pulse:** Yahoo Finance public chart endpoint (`^NSEI`, `^BSESN`, `INR=X`, `BZ=F`). Unofficial; if it breaks the tiles show "n/a".
- AI: Google Gemini API (`GEMINI_API_KEY` secret).

## Edit without touching code
`config/topics.yaml` (what's "big", watchlist, min score) · `config/sources.yaml` (feeds + tier).

## Secrets (GitHub → Settings → Secrets, set by `./setup.sh owner/repo`)
`GEMINI_API_KEY`, `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `MAIL_TO` (comma-separate for several), `NTFY_TOPIC`.

## Phone alerts
Push via the free ntfy app (subscribe to your `NTFY_TOPIC`). Email subjects starting 🔴 are Big Moves. Gmail filter: Settings → Filters → Create → *Has the words:* `subject:🔴` → Star it, Mark as important, Never send to spam.

## Run it manually
Actions tab → Market Radar → Run workflow (mode `run` or `weekly`).
