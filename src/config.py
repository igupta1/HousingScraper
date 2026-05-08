import os
from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")
ALERT_TO_EMAIL = os.environ.get("ALERT_TO_EMAIL", "")

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
RAPIDAPI_ZILLOW_HOST = os.environ.get("RAPIDAPI_ZILLOW_HOST", "zillow-com1.p.rapidapi.com")

DB_PATH = REPO_ROOT / "data" / "listings.db"

MIN_BEDS = 2
MAX_BEDS = 4
MIN_PRICE_PER_BED = 1500
MAX_PRICE_PER_BED = 2200

NEIGHBORHOODS = ["north beach", "nob hill", "russian hill"]

# Tight bbox covering North Beach + Nob Hill + Russian Hill (NE San Francisco).
BBOX = {
    "min_lat": 37.7900,
    "max_lat": 37.8100,
    "min_lon": -122.4250,
    "max_lon": -122.4050,
}

CRAIGSLIST_BASE_URL = "https://sfbay.craigslist.org/search/sfc/apa"

REDDIT_FEEDS = [
    "https://www.reddit.com/r/sfhousing/new/.rss",
    "https://www.reddit.com/r/sanfrancisco/search.rss?q=rent+OR+rental+OR+apartment&restrict_sr=on&sort=new&t=week",
]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def min_total_rent() -> int:
    return MIN_PRICE_PER_BED * MIN_BEDS


def max_total_rent() -> int:
    return MAX_PRICE_PER_BED * MAX_BEDS
