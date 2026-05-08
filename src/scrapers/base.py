import logging
from abc import ABC, abstractmethod
from typing import List

from ..models import Listing


class Scraper(ABC):
    name: str

    def __init__(self):
        self.log = logging.getLogger(f"scraper.{self.name}")

    @abstractmethod
    def fetch(self) -> List[Listing]:
        """Return a list of (unfiltered, possibly already-seen) Listings."""
