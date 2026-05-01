"""
Tests for the scrapers package.

Run from backend/:  pytest test_scrapers.py -v

No Flask app/db fixture — scrapers don't touch the DB in this task.
All HTTP is mocked; no network calls.
"""

from datetime import date
from unittest.mock import patch, MagicMock

import pytest

from scrapers import SCRAPER_REGISTRY
from scrapers.base import BaseScraper, ScrapedJob
from scrapers.greenhouse import GreenhouseScraper
from scrapers.lever import LeverScraper


# ── ScrapedJob dataclass ────────────────────────────────────────────

class TestScrapedJob:
    def test_constructs_with_all_fields(self):
        j = ScrapedJob(
            external_id="abc",
            title="Software Engineer",
            location="Remote",
            description="Build things.",
            url="https://example.com/jobs/abc",
            date_posted=date(2024, 11, 12),
        )
        assert j.external_id == "abc"
        assert j.date_posted == date(2024, 11, 12)

    def test_date_posted_defaults_to_none(self):
        j = ScrapedJob(
            external_id="abc", title="t", location="l",
            description="d", url="u",
        )
        assert j.date_posted is None


# ── BaseScraper contract ────────────────────────────────────────────

class TestBaseScraper:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseScraper()


# ── GreenhouseScraper ───────────────────────────────────────────────

GREENHOUSE_FIXTURE = {
    "jobs": [
        {
            "id": 4567890,
            "title": "Senior Backend Engineer",
            "location": {"name": "San Francisco, CA"},
            "content": "Join our team&#x2014;we build &lt;great&gt; things.",
            "absolute_url": "https://boards.greenhouse.io/fake/jobs/4567890",
            "updated_at": "2024-11-12T18:05:22.123Z",
        },
        {
            "id": 4567891,
            "title": "Data Scientist",
            "location": {"name": "Remote"},
            "content": "Analyze data.",
            "absolute_url": "https://boards.greenhouse.io/fake/jobs/4567891",
            "updated_at": "2024-11-11T09:00:00Z",
        },
    ],
    "meta": {"total": 2},
}


class _FakeGreenhouse(GreenhouseScraper):
    company_slug = "fake"
    board_token = "fake"


class TestGreenhouseScraper:
    def test_scrape_parses_response(self):
        fake_resp = MagicMock()
        fake_resp.json.return_value = GREENHOUSE_FIXTURE
        fake_resp.raise_for_status.return_value = None

        with patch("scrapers.greenhouse.requests.get", return_value=fake_resp) as mock_get:
            jobs = _FakeGreenhouse().scrape()

        mock_get.assert_called_once()
        url_called = mock_get.call_args[0][0]
        assert "fake" in url_called
        assert mock_get.call_args.kwargs["params"] == {"content": "true"}
        assert mock_get.call_args.kwargs["timeout"] == 15

        assert len(jobs) == 2
        first = jobs[0]
        assert first.external_id == "4567890"
        assert first.title == "Senior Backend Engineer"
        assert first.location == "San Francisco, CA"
        assert first.url == "https://boards.greenhouse.io/fake/jobs/4567890"
        assert first.date_posted == date(2024, 11, 12)
        # HTML entities unescaped
        assert "—" in first.description
        assert "<great>" in first.description

    def test_scrape_handles_empty_jobs(self):
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"jobs": [], "meta": {"total": 0}}
        fake_resp.raise_for_status.return_value = None

        with patch("scrapers.greenhouse.requests.get", return_value=fake_resp):
            jobs = _FakeGreenhouse().scrape()
        assert jobs == []


# ── LeverScraper ────────────────────────────────────────────────────

LEVER_FIXTURE = [
    {
        "id": "abc-123-def",
        "text": "Frontend Engineer",
        "categories": {
            "location": "New York",
            "team": "Web",
            "commitment": "Full-time",
        },
        "descriptionPlain": "Build UIs.",
        "description": "<p>Build UIs.</p>",
        "hostedUrl": "https://jobs.lever.co/fake/abc-123-def",
        "createdAt": 1699999200000,  # 2023-11-14 in UTC
    },
    {
        "id": "xyz-789",
        "text": "ML Engineer",
        "categories": {"location": "Remote"},
        "descriptionPlain": "Train models.",
        "hostedUrl": "https://jobs.lever.co/fake/xyz-789",
        "createdAt": 1700000000000,
    },
]


class _FakeLever(LeverScraper):
    company_slug = "fake"
    lever_company = "fake"


class TestLeverScraper:
    def test_scrape_parses_response(self):
        fake_resp = MagicMock()
        fake_resp.json.return_value = LEVER_FIXTURE
        fake_resp.raise_for_status.return_value = None

        with patch("scrapers.lever.requests.get", return_value=fake_resp) as mock_get:
            jobs = _FakeLever().scrape()

        mock_get.assert_called_once()
        assert mock_get.call_args.kwargs["params"] == {"mode": "json"}
        assert mock_get.call_args.kwargs["timeout"] == 15

        assert len(jobs) == 2
        first = jobs[0]
        assert first.external_id == "abc-123-def"
        assert first.title == "Frontend Engineer"
        assert first.location == "New York"
        assert first.description == "Build UIs."
        assert first.url == "https://jobs.lever.co/fake/abc-123-def"
        assert first.date_posted is not None

    def test_scrape_handles_empty_list(self):
        fake_resp = MagicMock()
        fake_resp.json.return_value = []
        fake_resp.raise_for_status.return_value = None

        with patch("scrapers.lever.requests.get", return_value=fake_resp):
            jobs = _FakeLever().scrape()
        assert jobs == []


# ── Registry ────────────────────────────────────────────────────────

class TestRegistry:
    def test_has_six_scrapers(self):
        assert len(SCRAPER_REGISTRY) == 6

    def test_slugs_are_unique(self):
        slugs = [s.company_slug for s in SCRAPER_REGISTRY]
        assert len(set(slugs)) == len(slugs)

    def test_slugs_match_expected(self):
        slugs = {s.company_slug for s in SCRAPER_REGISTRY}
        assert slugs == {"airbnb", "stripe", "coinbase", "spotify", "palantir", "plaid"}

    def test_all_are_base_scrapers(self):
        assert all(isinstance(s, BaseScraper) for s in SCRAPER_REGISTRY)
