from typing import List, Optional

import httpx

from .. import config
from ..models import Listing
from .base import Scraper


def _to_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _within_bbox(lat, lon) -> bool:
    if lat is None or lon is None:
        return True  # don't drop listings whose coords are missing
    return (
        config.BBOX["min_lat"] <= lat <= config.BBOX["max_lat"]
        and config.BBOX["min_lon"] <= lon <= config.BBOX["max_lon"]
    )


class ZillowScraper(Scraper):
    """Talks to RapidAPI's `zillow-com1` /propertyExtendedSearch endpoint.

    Free tier (Basic plan) is typically ~500 req/mo. We call once per
    invocation, so polling every 2h gives ~360 req/mo with safety margin.
    """

    name = "zillow"

    def fetch(self) -> List[Listing]:
        if not config.RAPIDAPI_KEY:
            self.log.info("RAPIDAPI_KEY not set — skipping Zillow")
            return []

        url = f"https://{config.RAPIDAPI_ZILLOW_HOST}/propertyExtendedSearch"
        params = {
            "location": "San Francisco, CA",
            "status_type": "ForRent",
            "home_type": "Apartments,Houses,Townhomes,Multi-family,Condos",
            "bedsMin": str(config.MIN_BEDS),
            "bedsMax": str(config.MAX_BEDS),
            "rentMinPrice": str(config.min_total_rent()),
            "rentMaxPrice": str(config.max_total_rent()),
        }
        headers = {
            "X-RapidAPI-Key": config.RAPIDAPI_KEY,
            "X-RapidAPI-Host": config.RAPIDAPI_ZILLOW_HOST,
        }

        try:
            resp = httpx.get(url, params=params, headers=headers, timeout=30.0)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            body = e.response.text[:200] if e.response is not None else ""
            self.log.warning("zillow rapidapi http %s: %s",
                             e.response.status_code if e.response else "?", body)
            return []
        except httpx.HTTPError as e:
            self.log.warning("zillow rapidapi error: %s", e)
            return []

        try:
            data = resp.json()
        except ValueError:
            self.log.warning("zillow rapidapi returned non-JSON")
            return []

        # zillow-com1 returns {"props": [...], "totalResultCount": N, ...}
        props = data.get("props") or data.get("results") or []
        listings: List[Listing] = []
        for p in props:
            zpid = p.get("zpid") or p.get("id")
            if not zpid:
                continue
            url_path = p.get("detailUrl") or f"/homedetails/{zpid}_zpid/"
            full_url = (
                url_path if url_path.startswith("http")
                else f"https://www.zillow.com{url_path}"
            )

            price = _to_int(p.get("price"))
            beds = _to_int(p.get("bedrooms"))
            baths = _to_float(p.get("bathrooms"))
            lat = _to_float(p.get("latitude"))
            lon = _to_float(p.get("longitude"))
            address = p.get("address")

            if not _within_bbox(lat, lon):
                continue

            listings.append(
                Listing(
                    source="zillow",
                    listing_id=str(zpid),
                    url=full_url,
                    title=address or f"Zillow listing {zpid}",
                    price=price,
                    bedrooms=beds,
                    bathrooms=baths,
                    neighborhood=None,
                    address=address,
                    raw_text="",
                )
            )

        self.log.info("zillow: %d listings inside bbox (of %d returned)",
                      len(listings), len(props))
        return listings
