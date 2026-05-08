import json
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from .. import config
from ..models import Listing
from .base import Scraper


_PRICE_RE = re.compile(r"[\d,]+")
_ID_RE = re.compile(r"/(\d{8,})\.html")


def _build_url() -> str:
    center_lat = (config.BBOX["min_lat"] + config.BBOX["max_lat"]) / 2
    center_lon = (config.BBOX["min_lon"] + config.BBOX["max_lon"]) / 2
    params = {
        "min_bedrooms": config.MIN_BEDS,
        "max_bedrooms": config.MAX_BEDS,
        "min_price": config.min_total_rent(),
        "max_price": config.max_total_rent(),
        "lat": f"{center_lat:.4f}",
        "lon": f"{center_lon:.4f}",
        "search_distance": "1",
        "postal": "94133",
    }
    return f"{config.CRAIGSLIST_BASE_URL}?{urlencode(params)}"


def _parse_price(s: str) -> Optional[int]:
    if not s:
        return None
    m = _PRICE_RE.search(s)
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _build_metadata_index(json_ld: dict) -> Dict[str, Dict]:
    """Map listing title -> {beds, baths, lat, lon, address} from JSON-LD."""
    out: Dict[str, Dict] = {}
    items = json_ld.get("itemListElement") or []
    for entry in items:
        item = entry.get("item") or {}
        name = (item.get("name") or "").strip()
        if not name:
            continue
        addr = item.get("address") or {}
        out[name] = {
            "beds": item.get("numberOfBedrooms"),
            "baths": item.get("numberOfBathroomsTotal"),
            "lat": item.get("latitude"),
            "lon": item.get("longitude"),
            "locality": addr.get("addressLocality"),
            "street": addr.get("streetAddress"),
        }
    return out


def _extract_listing(card, meta_index: Dict[str, Dict]) -> Optional[Listing]:
    a = card.find("a", href=True)
    if not a:
        return None
    url = a["href"]
    if not url.startswith("http"):
        url = "https://sfbay.craigslist.org" + url
    id_match = _ID_RE.search(url)
    if not id_match:
        return None
    listing_id = id_match.group(1)

    title_el = card.find(class_="title")
    price_el = card.find(class_="price")
    location_el = card.find(class_="location")
    title = title_el.get_text(strip=True) if title_el else ""
    price = _parse_price(price_el.get_text(strip=True)) if price_el else None
    location = location_el.get_text(strip=True) if location_el else None

    meta = meta_index.get(title, {})
    beds = meta.get("beds")
    baths = meta.get("baths")
    address = meta.get("street") or None
    raw = " ".join(filter(None, [title, location, address]))

    return Listing(
        source="craigslist",
        listing_id=listing_id,
        url=url,
        title=title or "(untitled)",
        price=price,
        bedrooms=int(beds) if beds is not None else None,
        bathrooms=float(baths) if baths is not None else None,
        neighborhood=location,
        address=address,
        raw_text=raw,
    )


class CraigslistScraper(Scraper):
    name = "craigslist"

    def fetch(self) -> List[Listing]:
        url = _build_url()
        self.log.info("fetching %s", url)
        try:
            resp = httpx.get(
                url,
                headers={
                    "User-Agent": config.USER_AGENT,
                    "Accept": (
                        "text/html,application/xhtml+xml,"
                        "application/xml;q=0.9,*/*;q=0.8"
                    ),
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=30.0,
                follow_redirects=True,
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            self.log.warning("craigslist fetch failed: %s", e)
            return []

        soup = BeautifulSoup(resp.text, "lxml")

        json_ld: dict = {}
        results_script = soup.find("script", id="ld_searchpage_results")
        if results_script and results_script.string:
            try:
                json_ld = json.loads(results_script.string)
            except json.JSONDecodeError:
                self.log.warning("could not parse JSON-LD; bedroom data will be missing")

        meta_index = _build_metadata_index(json_ld)
        cards = soup.find_all("li", class_="cl-static-search-result")
        listings: List[Listing] = []
        for card in cards:
            listing = _extract_listing(card, meta_index)
            if listing:
                listings.append(listing)

        self.log.info("craigslist: parsed %d cards (%d w/ bedroom data)",
                      len(listings),
                      sum(1 for l in listings if l.bedrooms is not None))
        return listings
