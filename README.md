# SF Apartment Monitor

Polls Craigslist, Reddit, and Zillow for new SF rental listings in **North Beach / Nob Hill / Russian Hill**, filters to **2-bedroom** units at **$1,500–$2,500 per bedroom** ($3,000–$5,000 total), and emails new matches as a digest.

## Architecture

Two GitHub Actions workflows on different schedules, sharing state via a SQLite file checked into the repo:

| Workflow | Schedule | Sources | Sends email? |
|---|---|---|---|
| `fast.yml` | every 15 min | Craigslist + Reddit | ✅ digest of all new (incl. Zillow) |
| `zillow.yml` | once daily (12:00 UTC) | Zillow (RapidAPI) | ❌ inserts only — fast tick emails |

The Zillow cron makes **3 neighborhood-scoped API calls per run** (Nob Hill / Russian Hill / North Beach via `real-estate-zillow-com` `/v1/search/rent`). At one run/day that's ~90 req/mo, comfortably under the 100/mo hard cap on the RapidAPI Basic free tier. Neighborhood-scoped queries return ~30× more in-bbox results than a single citywide query.

## Setup

### 1. Gmail app password

1. https://myaccount.google.com → Security → 2-Step Verification (turn on if not already)
2. https://myaccount.google.com/apppasswords → create one named "SF Apt Monitor"
3. Copy the 16-character password (spaces are cosmetic — strip them)

### 2. RapidAPI key (optional but recommended for Zillow)

1. Sign up at https://rapidapi.com (free)
2. Visit a Zillow API listing — `zillow-com1` by apimaker is the most popular
3. Subscribe to the **Basic (free)** plan
4. **Toggle the hard-limit switch on** so you can never accidentally incur charges
5. Copy your `X-RapidAPI-Key` from the dashboard

### 3. GitHub secrets

In your repo: Settings → Secrets and variables → Actions → New repository secret

| Name | Value |
|---|---|
| `GMAIL_USER` | Your sending Gmail address |
| `GMAIL_APP_PASSWORD` | The 16-char app password from step 1 |
| `ALERT_TO_EMAIL` | Comma-separated recipients, e.g. `you@example.com,someone-else@example.com` |
| `RAPIDAPI_KEY` | Your RapidAPI key (skip if not using Zillow) |
| `RAPIDAPI_ZILLOW_HOST` | `zillow-com1.p.rapidapi.com` |

### 4. First run

After pushing to GitHub, trigger the workflow manually once to verify:

- Actions tab → **fast-tick** → "Run workflow"
- Watch the log; you should see Craigslist/Reddit fetch counts and (if any matches) a digest email arrive

If it works, the cron takes over automatically.

## Local development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in .env

python -m src.main fast       # Craigslist + Reddit + email
python -m src.main zillow     # Zillow only
python -m src.main all        # everything + email
```

The SQLite dedupe DB lives at `data/listings.db`.

## Tweaking criteria

All knobs are in `src/config.py`:

- `MIN_BEDS` / `MAX_BEDS`
- `MIN_PRICE_PER_BED` / `MAX_PRICE_PER_BED`
- `BBOX` for the neighborhood bounding box
- `NEIGHBORHOODS` for the post-filter text match

## Caveats

- **Zillow** uses PerimeterX + Cloudflare and blocks GitHub Actions IPs directly. We use a third-party RapidAPI proxy as the only realistic free path. If `RAPIDAPI_KEY` isn't set, Zillow is silently skipped.
- **Craigslist** is rock-solid via RSS but listings can be re-posted under new IDs; same listing may notify twice in rare cases.
- **Reddit** is best-effort — posts are free-form text, so price/bed extraction is regex-based and imperfect. The neighborhood filter is strict (post must mention one of the 3) to avoid noise.
- The SQLite DB is committed back to the repo on every run. Over months this grows the repo modestly (KBs per row); periodic prune of `notified=1, first_seen < 90d` rows is a future improvement.
