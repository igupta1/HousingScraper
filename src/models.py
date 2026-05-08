from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class Listing:
    source: str
    listing_id: str
    url: str
    title: str
    price: Optional[int]
    bedrooms: Optional[int]
    bathrooms: Optional[float]
    neighborhood: Optional[str]
    address: Optional[str]
    posted_at: Optional[datetime] = None
    raw_text: str = ""

    @property
    def price_per_bedroom(self) -> Optional[float]:
        if self.price is None or not self.bedrooms:
            return None
        return self.price / self.bedrooms

    @property
    def dedup_key(self) -> str:
        return f"{self.source}:{self.listing_id}"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
