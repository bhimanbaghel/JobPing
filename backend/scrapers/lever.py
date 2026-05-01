from datetime import date
from typing import List, Optional

import requests

from .base import BaseScraper, ScrapedJob


class LeverScraper(BaseScraper):
    lever_company: str
    BASE_URL = "https://api.lever.co/v0/postings/{lever_company}"

    def scrape(self) -> List[ScrapedJob]:
        resp = requests.get(
            self.BASE_URL.format(lever_company=self.lever_company),
            params={"mode": "json"},
            timeout=15,
        )
        resp.raise_for_status()
        postings = resp.json()

        jobs: List[ScrapedJob] = []
        for item in postings:
            categories = item.get("categories") or {}
            jobs.append(
                ScrapedJob(
                    external_id=str(item["id"]),
                    title=item.get("text", ""),
                    location=categories.get("location", ""),
                    description=item.get("descriptionPlain") or item.get("description", ""),
                    url=item["hostedUrl"],
                    date_posted=_from_unix_ms(item.get("createdAt")),
                )
            )
        return jobs


def _from_unix_ms(value: Optional[int]):
    if value is None:
        return None
    return date.fromtimestamp(value / 1000)
