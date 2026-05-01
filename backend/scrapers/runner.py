import html
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from app.models import Job, db
from scrapers import SCRAPER_REGISTRY

logger = logging.getLogger(__name__)
_TAG_RE = re.compile(r"<[^>]+>")
_LINE_BREAK_TAG_RE = re.compile(r"(?i)<\s*br\s*/?\s*>")
_BLOCK_CLOSE_TAG_RE = re.compile(r"(?i)</\s*(p|div|section|article|ul|ol|li|h[1-6])\s*>")
_LI_OPEN_TAG_RE = re.compile(r"(?i)<\s*li\b[^>]*>")
_SCRIPT_STYLE_RE = re.compile(r"(?is)<\s*(script|style)\b[^>]*>.*?<\s*/\s*\1\s*>")
_SPACE_RUN_RE = re.compile(r"[ \t]+")
_BLANK_LINE_RE = re.compile(r"\n{3,}")


def parse_location(raw: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if not raw or not raw.strip():
        return (None, None, None)

    parts = [p.strip() for p in raw.split(",")]
    parts = [p for p in parts if p]

    if not parts:
        return (None, None, None)
    if len(parts) == 1:
        return (parts[0], None, None)
    if len(parts) == 2:
        return (parts[0], parts[1], None)
    return (parts[0], parts[1], ", ".join(parts[2:]))


def clean_description(raw: str) -> str:
    if not raw:
        return ""
    text = (
        html.unescape(raw)
        .replace("\xa0", " ")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    text = _SCRIPT_STYLE_RE.sub(" ", text)
    text = _LINE_BREAK_TAG_RE.sub("\n", text)
    text = _BLOCK_CLOSE_TAG_RE.sub("\n", text)
    text = _LI_OPEN_TAG_RE.sub("\n- ", text)
    text = _TAG_RE.sub(" ", text)
    text = _SPACE_RUN_RE.sub(" ", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)
    text = _BLANK_LINE_RE.sub("\n\n", text)
    return text.strip()


def run_single_scraper(scraper) -> dict:
    slug = scraper.company_slug
    now = datetime.now(timezone.utc)

    scraped_jobs = scraper.scrape()
    fetched = len(scraped_jobs)

    existing_by_eid = {
        j.external_id: j
        for j in Job.query.filter_by(company=slug).all()
    }

    seen_external_ids: set[str] = set()
    inserted = 0
    updated = 0

    for sj in scraped_jobs:
        seen_external_ids.add(sj.external_id)
        city, state, country = parse_location(sj.location)
        description = clean_description(sj.description)

        existing = existing_by_eid.get(sj.external_id)
        if existing is not None:
            existing.role = sj.title
            existing.description = description
            existing.link = sj.url
            existing.city = city
            existing.state = state
            existing.country = country
            existing.posted_at = sj.date_posted
            existing.is_active = True
            existing.last_seen_at = now
            updated += 1
        else:
            db.session.add(Job(
                company=slug,
                external_id=sj.external_id,
                role=sj.title,
                description=description,
                link=sj.url,
                city=city,
                state=state,
                country=country,
                posted_at=sj.date_posted,
                is_active=True,
                last_seen_at=now,
            ))
            inserted += 1

    deactivated = 0
    if seen_external_ids:
        deactivated = Job.query.filter(
            Job.company == slug,
            Job.external_id.notin_(seen_external_ids),
            Job.is_active == True,  # noqa: E712 — SQLAlchemy needs == for column comparison
        ).update(
            {Job.is_active: False, Job.last_seen_at: now},
            synchronize_session=False,
        )
    else:
        logger.warning(
            "%s: scrape() returned 0 jobs — skipping staleness sweep to avoid mass-deactivation",
            slug,
        )

    db.session.commit()

    stats = {
        "slug": slug,
        "fetched": fetched,
        "inserted": inserted,
        "updated": updated,
        "deactivated": deactivated,
    }
    logger.info(
        "%s: fetched=%d inserted=%d updated=%d deactivated=%d",
        slug, fetched, inserted, updated, deactivated,
    )
    return stats


def run_all_scrapers() -> list[dict]:
    results: list[dict] = []
    for scraper in SCRAPER_REGISTRY:
        slug = getattr(scraper, "company_slug", "<unknown>")
        try:
            results.append(run_single_scraper(scraper))
        except Exception as e:
            db.session.rollback()
            logger.error("Scraper %s failed: %s", slug, e, exc_info=True)
            results.append({"slug": slug, "error": str(e)})
    return results
