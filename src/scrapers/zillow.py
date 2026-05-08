import re
from typing import Dict, List, Optional

import httpx

from .. import config
from ..models import Listing
from .base import Scraper


_PRICE_DIGITS = re.compile(r"[\d,]+")


def _parse_price(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    m = _PRICE_DIGITS.search(str(value))
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _parse_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None


def _parse_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _within_bbox(lat, lon) -> bool:
    if lat is None or lon is None:
        return False
    return (
        config.BBOX["min_lat"] <= lat <= config.BBOX["max_lat"]
        and config.BBOX["min_lon"] <= lon <= config.BBOX["max_lon"]
    )


def _absolute_url(detail_url: str) -> str:
    if not detail_url:
        return ""
    return detail_url if detail_url.startswith("http") else "https://www.zillow.com" + detail_url


def _expand(item: dict, neighborhood_label: str) -> List[Listing]:
    lat_long = item.get("latLong") or {}
    lat = _parse_float(lat_long.get("latitude"))
    lon = _parse_float(lat_long.get("longitude"))
    if not _within_bbox(lat, lon):
        return []

    zpid = item.get("zpid") or item.get("id")
    if not zpid:
        return []

    url = _absolute_url(item.get("detailUrl") or "")
    address = item.get("address") or item.get("addressStreet")
    title = item.get("buildingName") or address or f"Zillow {zpid}"

    out: List[Listing] = []
    units = item.get("units")

    if units and item.get("isBuilding"):
        for unit in units:
            beds = _parse_int(unit.get("beds"))
            price = _parse_price(unit.get("price"))
            if beds is None:
                continue
            out.append(Listing(
                source="zillow",
                listing_id=f"{zpid}-{beds}br",
                url=url,
                title=title,
                price=price,
                bedrooms=beds,
                bathrooms=None,
                neighborhood=neighborhood_label,
                address=address,
            ))
    else:
        beds = _parse_int(item.get("beds") or item.get("bedrooms"))
        baths = _parse_float(item.get("baths") or item.get("bathrooms"))
        price = (
            _parse_price(item.get("unformattedPrice"))
            or _parse_price(item.get("price"))
        )
        out.append(Listing(
            source="zillow",
            listing_id=str(zpid),
            url=url,
            title=title,
            price=price,
            bedrooms=beds,
            bathrooms=baths,
            neighborhood=neighborhood_label,
            address=address,
        ))

    return out


_NEIGHBORHOOD_QUERIES = [
    ("Nob Hill", "Nob Hill, San Francisco, CA"),
    ("Russian Hill", "Russian Hill, San Francisco, CA"),
    ("North Beach", "North Beach, San Francisco, CA"),
]


class ZillowScraper(Scraper):
    """Real Estate Zillow.Com (RapidAPI) /v1/search/rent.

    Free Basic tier is 100 req/mo (hard limit). We make 3 neighborhood-scoped
    calls per invocation, so polling once per day = ~90 req/mo with margin.
    """

    name = "zillow"

    def fetch(self) -> List[Listing]:
        if not config.RAPIDAPI_KEY:
            self.log.info("RAPIDAPI_KEY not set — skipping Zillow")
            return []

        url = f"https://{config.RAPIDAPI_ZILLOW_HOST}/v1/search/rent"
        headers = {
            "x-rapidapi-host": config.RAPIDAPI_ZILLOW_HOST,
            "x-rapidapi-key": config.RAPIDAPI_KEY,
        }

        seen_keys: set = set()
        all_listings: List[Listing] = []

        for label, query in _NEIGHBORHOOD_QUERIES:
            try:
                resp = httpx.get(
                    url,
                    params={"location_or_rid": query, "page": "1"},
                    headers=headers,
                    timeout=30.0,
                )
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                body = e.response.text[:200] if e.response is not None else ""
                self.log.warning(
                    "zillow %s http %s: %s",
                    label,
                    e.response.status_code if e.response else "?",
                    body,
                )
                continue
            except httpx.HTTPError as e:
                self.log.warning("zillow %s error: %s", label, e)
                continue

            try:
                payload = resp.json()
            except ValueError:
                self.log.warning("zillow %s returned non-JSON", label)
                continue

            items = (payload.get("data") or {}).get("listings") or []
            new_for_label = 0
            for item in items:
                for listing in _expand(item, label):
                    if listing.dedup_key in seen_keys:
                        continue
                    seen_keys.add(listing.dedup_key)
                    all_listings.append(listing)
                    new_for_label += 1
            self.log.info(
                "zillow %s: %d items -> %d unique in-bbox listings",
                label, len(items), new_for_label,
            )

        self.log.info("zillow total: %d unique listings", len(all_listings))
        return all_listings
