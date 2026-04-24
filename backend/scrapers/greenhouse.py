import html
from datetime import datetime
from typing import List, Optional

import requests

from .base import BaseScraper, ScrapedJob


class GreenhouseScraper(BaseScraper):
    board_token: str
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"

    def scrape(self) -> List[ScrapedJob]:
        resp = requests.get(
            self.BASE_URL.format(board_token=self.board_token),
            params={"content": "true"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        jobs: List[ScrapedJob] = []
        for item in data.get("jobs", []):
            jobs.append(
                ScrapedJob(
                    external_id=str(item["id"]),
                    title=item["title"],
                    location=(item.get("location") or {}).get("name", ""),
                    description=html.unescape(item.get("content") or ""),
                    url=item["absolute_url"],
                    date_posted=_parse_iso_date(item.get("updated_at")),
                )
            )
        return jobs


def _parse_iso_date(value: Optional[str]):
    if not value:
        return None
    # Greenhouse returns e.g. "2024-11-12T18:05:22.123Z" — datetime.fromisoformat
    # handles the offset form in 3.11+, but not the trailing "Z", so normalize.
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).date()
