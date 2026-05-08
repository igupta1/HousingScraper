from typing import Iterable, List

from . import config
from .models import Listing


_NEIGHBORHOOD_TOKENS = {
    "north beach": ["north beach"],
    "nob hill": ["nob hill"],
    "russian hill": ["russian hill"],
}

# Tokens that strongly indicate a listing is NOT in our target set even if it
# falls inside the bounding box.
_EXCLUDE_TOKENS = [
    "telegraph hill",
    "chinatown",
    "fisherman",
    "financial district",
    "fidi",
    "polk gulch",
    "marina",
    "pacific heights",
    "pac heights",
    "tenderloin",
]


def _haystack(listing: Listing) -> str:
    parts = [
        listing.title or "",
        listing.neighborhood or "",
        listing.address or "",
        listing.raw_text or "",
    ]
    return " ".join(parts).lower()


def matches_neighborhood(listing: Listing) -> bool:
    text = _haystack(listing)
    if any(tok in text for tokens in _NEIGHBORHOOD_TOKENS.values() for tok in tokens):
        return True
    if any(tok in text for tok in _EXCLUDE_TOKENS):
        return False
    # No explicit signal either way — accept (the bbox already narrowed it).
    return True


def matches_criteria(listing: Listing) -> bool:
    if listing.bedrooms is None or listing.price is None:
        return False
    if not (config.MIN_BEDS <= listing.bedrooms <= config.MAX_BEDS):
        return False
    ppb = listing.price_per_bedroom
    if ppb is None:
        return False
    if not (config.MIN_PRICE_PER_BED <= ppb <= config.MAX_PRICE_PER_BED):
        return False
    return matches_neighborhood(listing)


def apply(listings: Iterable[Listing]) -> List[Listing]:
    return [l for l in listings if matches_criteria(l)]
