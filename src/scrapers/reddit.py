import re
from typing import List, Optional

import feedparser
import httpx

from .. import config
from ..models import Listing
from .base import Scraper


_PRICE_RE = re.compile(r"\$\s?([\d,]{3,6})(?:\s*/?\s*(?:mo|month|m))?", re.IGNORECASE)
_BED_RE = re.compile(r"(\d+)\s*(?:br|bed|bedroom|bdr)s?", re.IGNORECASE)
_NEIGHBORHOODS = {
    "north beach": "North Beach",
    "nob hill": "Nob Hill",
    "russian hill": "Russian Hill",
}
_ROOMMATE_TOKENS = ("roommate", "/room", "per room", "looking for room")


def _extract_price(text: str) -> Optional[int]:
    """Largest $-figure in the text — usually the rent."""
    candidates = []
    for m in _PRICE_RE.finditer(text):
        try:
            candidates.append(int(m.group(1).replace(",", "")))
        except ValueError:
            pass
    candidates = [c for c in candidates if 500 <= c <= 25000]
    return max(candidates) if candidates else None


def _extract_beds(text: str) -> Optional[int]:
    m = _BED_RE.search(text)
    if m:
        try:
            beds = int(m.group(1))
            if 0 < beds < 10:
                return beds
        except ValueError:
            pass
    return None


def _extract_neighborhood(text: str) -> Optional[str]:
    lowered = text.lower()
    for needle, label in _NEIGHBORHOODS.items():
        if needle in lowered:
            return label
    return None


def _is_roommate_post(text: str) -> bool:
    lowered = text.lower()
    return any(tok in lowered for tok in _ROOMMATE_TOKENS)


class RedditScraper(Scraper):
    name = "reddit"

    def fetch(self) -> List[Listing]:
        listings: List[Listing] = []
        for feed_url in config.REDDIT_FEEDS:
            listings.extend(self._fetch_one(feed_url))
        self.log.info("reddit: %d entries across %d feeds",
                      len(listings), len(config.REDDIT_FEEDS))
        return listings

    def _fetch_one(self, feed_url: str) -> List[Listing]:
        self.log.info("fetching %s", feed_url)
        try:
            resp = httpx.get(
                feed_url,
                headers={"User-Agent": config.USER_AGENT},
                timeout=20.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            self.log.warning("reddit fetch failed (%s): %s", feed_url, e)
            return []

        parsed = feedparser.parse(resp.content)
        out: List[Listing] = []
        for entry in parsed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            entry_id = entry.get("id", link)
            summary = entry.get("summary", "")
            haystack = f"{title} {summary}"

            if _is_roommate_post(haystack):
                # Roommate-only posts can be valid (single room rent), but
                # they often advertise the room price not the unit price.
                # Skip — Craigslist+Zillow cover whole-unit rentals better.
                continue

            neighborhood = _extract_neighborhood(haystack)
            if neighborhood is None:
                # Reddit's SF subs cover the whole city; if no neighborhood
                # match, drop early to avoid noise.
                continue

            price = _extract_price(haystack)
            beds = _extract_beds(haystack)

            out.append(
                Listing(
                    source="reddit",
                    listing_id=entry_id,
                    url=link,
                    title=title,
                    price=price,
                    bedrooms=beds,
                    bathrooms=None,
                    neighborhood=neighborhood,
                    address=None,
                    raw_text=summary,
                )
            )
        return out
