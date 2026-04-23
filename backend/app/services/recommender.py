"""Job-recommendation engine.

Pipeline (FR6, US-6):

  1. Read the user's preferences (must have at least one role — FR6.1).
  2. Filter the ``jobs`` table by case-insensitive role match (always)
     and company match (when companies were specified).
  3. Compute / fetch a 384-dim vector for the user (resume if uploaded,
     otherwise a synthesized preferences string — FR6.3) and ensure
     each candidate job has a cached vector.
  4. Score each candidate by cosine similarity, keep ``score >= 0.80``
     and persist the surviving rows into the ``recommendations`` table
     (Table 3) for the requesting user.
  5. Return the rows sorted descending by similarity (FR6.4).

Public surface:

  - ``recommend_for_user(user_id)``      – recompute + persist + return
  - ``get_existing_recommendations(uid)`` – read-only fetch from Table 3
  - ``MissingRolePreferences``           – raised when FR6.1 is violated
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional, Tuple

import numpy as np
from sqlalchemy import func, or_

from app.models import (
    db,
    Job,
    JobEmbedding,
    Recommendation,
    Resume,
    ResumeEmbedding,
    UserPreference,
)
from app.services.embeddings import (
    upsert_job_embedding,
    upsert_resume_embedding,
)

SIMILARITY_THRESHOLD = 0.80


class RecommenderError(Exception):
    pass


class MissingRolePreferences(RecommenderError):
    """FR6.1 — at least one preferred role is required."""


@dataclass
class JobRecommendation:
    job_id: int
    role: str
    company: str
    description: str
    link: Optional[str]
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    salary_usd: Optional[float]
    posted_at: Optional[str]
    similarity_score: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["location"] = {
            "city": d.pop("city"),
            "state": d.pop("state"),
            "country": d.pop("country"),
        }
        return d


# ───────────────────────────── helpers ──────────────────────────────────────
def _user_preferences(user_id: int) -> UserPreference:
    pref = (
        db.session.query(UserPreference)
        .filter_by(user_id=user_id)
        .one_or_none()
    )
    if pref is None or not list(pref.roles or []):
        raise MissingRolePreferences(
            "At least one preferred job role is required to generate recommendations."
        )
    return pref


def _synthesize_preferences_text(pref: UserPreference) -> str:
    roles = ", ".join(pref.roles or []) or "any"
    companies = ", ".join(pref.companies or []) or "any"
    locations = ", ".join(pref.locations or []) or "any"
    return (
        f"Looking for roles: {roles}. "
        f"Preferred companies: {companies}. "
        f"Preferred locations: {locations}."
    )


def _compute_user_vector(user_id: int, pref: UserPreference) -> Tuple[List[float], str]:
    """Return (vector, source) and refresh the ResumeEmbedding cache."""
    resume = (
        db.session.query(Resume).filter_by(user_id=user_id).one_or_none()
    )
    if resume is not None and (resume.parsed_text or "").strip():
        upsert_resume_embedding(
            db.session, user_id, resume.parsed_text, source="resume"
        )
        source = "resume"
    else:
        upsert_resume_embedding(
            db.session,
            user_id,
            _synthesize_preferences_text(pref),
            source="preferences",
        )
        source = "preferences"
    db.session.flush()
    emb = db.session.get(ResumeEmbedding, user_id)
    return list(emb.embedding), source


def _filter_candidate_jobs(roles: List[str], companies: List[str]) -> List[Job]:
    role_filters = [
        func.lower(Job.role).contains(r.lower()) for r in roles if r
    ]
    if not role_filters:
        return []
    q = db.session.query(Job).filter(or_(*role_filters))

    company_filters = [
        func.lower(Job.company).contains(c.lower()) for c in companies if c
    ]
    if company_filters:
        q = q.filter(or_(*company_filters))
    return q.all()


def _ensure_job_vector(job: Job) -> List[float]:
    emb = db.session.get(JobEmbedding, job.id)
    if emb is None:
        upsert_job_embedding(db.session, job.id, job.description or "")
        db.session.flush()
        emb = db.session.get(JobEmbedding, job.id)
    return list(emb.embedding)


def _to_dto(job: Job, score: float) -> JobRecommendation:
    return JobRecommendation(
        job_id=job.id,
        role=job.role,
        company=job.company,
        description=job.description,
        link=job.link,
        city=job.city,
        state=job.state,
        country=job.country,
        salary_usd=float(job.salary_usd) if job.salary_usd is not None else None,
        posted_at=job.posted_at.isoformat() if job.posted_at else None,
        similarity_score=score,
    )


# ───────────────────────────── public api ───────────────────────────────────
def recommend_for_user(
    user_id: int, threshold: float = SIMILARITY_THRESHOLD
) -> List[JobRecommendation]:
    """Recompute recommendations for ``user_id`` and persist them.

    Raises :class:`MissingRolePreferences` if FR6.1 is violated.
    """
    pref = _user_preferences(user_id)
    user_vec, _source = _compute_user_vector(user_id, pref)

    candidates = _filter_candidate_jobs(
        list(pref.roles or []), list(pref.companies or [])
    )

    # Always wipe stale rows for this user; we'll repopulate below.
    db.session.query(Recommendation).filter_by(user_id=user_id).delete(
        synchronize_session=False
    )

    if not candidates:
        db.session.commit()
        return []

    user_arr = np.asarray(user_vec, dtype=np.float32)
    user_norm = float(np.linalg.norm(user_arr))
    if user_norm == 0.0:
        db.session.commit()
        return []

    scored: List[Tuple[Job, float]] = []
    for job in candidates:
        job_vec = _ensure_job_vector(job)
        job_arr = np.asarray(job_vec, dtype=np.float32)
        job_norm = float(np.linalg.norm(job_arr))
        if job_norm == 0.0:
            continue
        cos = float(np.dot(user_arr, job_arr) / (user_norm * job_norm))
        if cos >= threshold:
            scored.append((job, cos))

    scored.sort(key=lambda t: t[1], reverse=True)

    for job, score in scored:
        db.session.add(
            Recommendation(
                user_id=user_id, job_id=job.id, similarity_score=score
            )
        )
    db.session.commit()
    return [_to_dto(job, score) for job, score in scored]


def get_existing_recommendations(user_id: int) -> List[JobRecommendation]:
    """Read recommendations from Table 3 without recomputing."""
    rows = (
        db.session.query(Recommendation, Job)
        .join(Job, Recommendation.job_id == Job.id)
        .filter(Recommendation.user_id == user_id)
        .order_by(Recommendation.similarity_score.desc())
        .all()
    )
    return [_to_dto(job, rec.similarity_score) for rec, job in rows]
