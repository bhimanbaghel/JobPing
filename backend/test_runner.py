"""Tests for scrapers.runner — parse_location (pure) and the DB-writing runner.

Run from backend/:  pytest test_runner.py -v
"""

import logging
from datetime import date, datetime, timezone

import pytest

from app import create_app
from app.models import Job, db
from scrapers.base import ScrapedJob
from scrapers.runner import (
    clean_description,
    parse_location,
    run_all_scrapers,
    run_single_scraper,
)


# ── parse_location ──────────────────────────────────────────────────

class TestParseLocation:
    def test_empty_string(self):
        assert parse_location("") == (None, None, None)

    def test_whitespace_only(self):
        assert parse_location("   ") == (None, None, None)

    def test_single_part(self):
        assert parse_location("Remote") == ("Remote", None, None)

    def test_two_parts(self):
        assert parse_location("San Francisco, CA") == ("San Francisco", "CA", None)

    def test_three_parts(self):
        assert parse_location("New York, NY, USA") == ("New York", "NY", "USA")

    def test_more_than_three_parts(self):
        assert parse_location("Berlin, Berlin, Germany, EU") == (
            "Berlin",
            "Berlin",
            "Germany, EU",
        )

    def test_strips_whitespace(self):
        assert parse_location("  Paris ,  IdF , France ") == ("Paris", "IdF", "France")


class TestCleanDescription:
    def test_strips_html_and_unescapes_entities(self):
        raw = "<div>Hello&nbsp;<b>World</b> &amp; team</div>"
        assert clean_description(raw) == "Hello World & team"

    def test_preserves_readable_structure_for_breaks_and_lists(self):
        raw = (
            "<h2>About the role</h2>"
            "<p>Build systems<br/>with Python.</p>"
            "<ul><li>Design APIs</li><li>Improve reliability</li></ul>"
        )
        assert clean_description(raw) == (
            "About the role\n"
            "Build systems\n"
            "with Python.\n"
            "- Design APIs\n"
            "- Improve reliability"
        )


# ── Runner integration tests ────────────────────────────────────────

class FakeScraper:
    def __init__(self, slug: str, jobs: list[ScrapedJob], raises: Exception | None = None):
        self.company_slug = slug
        self._jobs = jobs
        self._raises = raises

    def scrape(self) -> list[ScrapedJob]:
        if self._raises is not None:
            raise self._raises
        return self._jobs


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _sj(eid: str, title: str = "Engineer", location: str = "San Francisco, CA, USA") -> ScrapedJob:
    return ScrapedJob(
        external_id=eid,
        title=title,
        location=location,
        description="desc",
        url=f"https://example.com/{eid}",
        date_posted=date(2026, 4, 1),
    )


class TestRunSingleScraper:
    def test_inserts_new_jobs(self, app):
        scraper = FakeScraper("airbnb", [_sj("101", "Backend"), _sj("102", "Frontend")])

        stats = run_single_scraper(scraper)

        assert stats == {
            "slug": "airbnb",
            "fetched": 2,
            "inserted": 2,
            "updated": 0,
            "deactivated": 0,
        }
        rows = Job.query.filter_by(company="airbnb").order_by(Job.external_id).all()
        assert len(rows) == 2
        r = rows[0]
        assert r.role == "Backend"
        assert r.description == "desc"
        assert r.link == "https://example.com/101"
        assert r.city == "San Francisco"
        assert r.state == "CA"
        assert r.country == "USA"
        assert r.posted_at == date(2026, 4, 1)
        assert r.is_active is True
        assert r.last_seen_at is not None

    def test_updates_existing_job(self, app):
        db.session.add(Job(
            company="airbnb",
            external_id="101",
            role="Old Title",
            description="old",
            link="https://old.example.com",
            is_active=True,
        ))
        db.session.commit()

        scraper = FakeScraper("airbnb", [_sj("101", "New Title")])
        stats = run_single_scraper(scraper)

        assert stats["inserted"] == 0
        assert stats["updated"] == 1
        rows = Job.query.filter_by(company="airbnb").all()
        assert len(rows) == 1
        assert rows[0].role == "New Title"
        assert rows[0].link == "https://example.com/101"
        assert rows[0].last_seen_at is not None

    def test_cleans_html_description_on_insert_and_update(self, app):
        scraper = FakeScraper(
            "airbnb",
            [
                ScrapedJob(
                    external_id="201",
                    title="Backend",
                    location="Remote",
                    description="<p>Build&nbsp;<b>APIs</b> &amp; services</p>",
                    url="https://example.com/201",
                    date_posted=date(2026, 4, 1),
                )
            ],
        )
        run_single_scraper(scraper)
        row = Job.query.filter_by(company="airbnb", external_id="201").one()
        assert row.description == "Build APIs & services"

        scraper2 = FakeScraper(
            "airbnb",
            [
                ScrapedJob(
                    external_id="201",
                    title="Backend",
                    location="Remote",
                    description="<div>Own <i>platform</i> reliability</div>",
                    url="https://example.com/201",
                    date_posted=date(2026, 4, 1),
                )
            ],
        )
        run_single_scraper(scraper2)
        row2 = Job.query.filter_by(company="airbnb", external_id="201").one()
        assert row2.description == "Own platform reliability"

    def test_deactivates_unseen_jobs(self, app):
        db.session.add_all([
            Job(company="airbnb", external_id="101", role="Kept",
                description="d", link="u", is_active=True),
            Job(company="airbnb", external_id="102", role="Stale",
                description="d", link="u", is_active=True),
        ])
        db.session.commit()

        scraper = FakeScraper("airbnb", [_sj("101", "Kept")])
        stats = run_single_scraper(scraper)

        assert stats["deactivated"] == 1
        kept = Job.query.filter_by(company="airbnb", external_id="101").one()
        stale = Job.query.filter_by(company="airbnb", external_id="102").one()
        assert kept.is_active is True
        assert stale.is_active is False
        assert stale.last_seen_at is not None

    def test_empty_scrape_skips_staleness(self, app, caplog):
        db.session.add_all([
            Job(company="airbnb", external_id="101", role="a",
                description="d", link="u", is_active=True),
            Job(company="airbnb", external_id="102", role="b",
                description="d", link="u", is_active=True),
        ])
        db.session.commit()

        scraper = FakeScraper("airbnb", [])
        with caplog.at_level(logging.WARNING, logger="scrapers.runner"):
            stats = run_single_scraper(scraper)

        assert stats["fetched"] == 0
        assert stats["deactivated"] == 0
        assert all(j.is_active for j in Job.query.filter_by(company="airbnb").all())
        assert any("skipping staleness sweep" in rec.message for rec in caplog.records)

    def test_scoped_to_company(self, app):
        """Running airbnb's scraper must not deactivate stripe's jobs."""
        db.session.add_all([
            Job(company="stripe", external_id="s1", role="r",
                description="d", link="u", is_active=True),
        ])
        db.session.commit()

        scraper = FakeScraper("airbnb", [_sj("a1")])
        run_single_scraper(scraper)

        stripe_job = Job.query.filter_by(company="stripe", external_id="s1").one()
        assert stripe_job.is_active is True


class TestRunAllScrapers:
    def test_failure_isolated_between_scrapers(self, app, monkeypatch):
        good = FakeScraper("airbnb", [_sj("101")])
        bad = FakeScraper("stripe", [], raises=RuntimeError("boom"))
        monkeypatch.setattr(
            "scrapers.runner.SCRAPER_REGISTRY",
            [bad, good],
        )

        results = run_all_scrapers()

        assert len(results) == 2
        bad_result = next(r for r in results if r["slug"] == "stripe")
        good_result = next(r for r in results if r["slug"] == "airbnb")
        assert "error" in bad_result and bad_result["error"] == "boom"
        assert good_result["inserted"] == 1

        # Good scraper's data was committed despite the other's failure
        assert Job.query.filter_by(company="airbnb").count() == 1
        assert Job.query.filter_by(company="stripe").count() == 0
