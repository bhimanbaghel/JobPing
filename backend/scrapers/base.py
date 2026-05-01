from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import List, Optional


@dataclass
class ScrapedJob:
    external_id: str
    title: str
    location: str
    description: str
    url: str
    date_posted: Optional[date] = None


class BaseScraper(ABC):
    company_slug: str

    @abstractmethod
    def scrape(self) -> List[ScrapedJob]:
        """Fetch and return all current job listings."""
        pass
