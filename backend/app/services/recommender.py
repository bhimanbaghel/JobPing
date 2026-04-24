"""Job-recommendation engine.

Pipeline (FR6, US-6):

  1. Read the user's preferences (must have at least one role — FR6.1).
  2. Filter the ``jobs`` table by case-insensitive role match (always)
     and company match (when companies were specified).
  3. If a resume exists, compute/fetch a resume vector and ensure each
     candidate job has a cached vector.
  4. Rank candidates:
       - no resume: by ``posted_at`` desc, then ``created_at`` desc
      - with resume: compute score, then final sort by recency
     and persist rows into the ``recommendations`` table.
  5. Return rows sorted by recency.

Public surface:

  - ``recommend_for_user(user_id)``      – recompute + persist + return
  - ``get_existing_recommendations(uid)`` – read-only fetch from Table 3
  - ``MissingRolePreferences``           – raised when FR6.1 is violated
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime
import re
from typing import List, Optional

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
_ROLE_NOISE_RE = re.compile(r"\([^)]*\)")
_ROLE_SPLIT_RE = re.compile(r"\s*(?:\||/|,| - | — )\s*")
_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#.\-]*")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "into", "is", "it", "of", "on", "or", "that", "the", "to", "with",
    "you", "your", "we", "our", "this", "will", "can", "have", "has",
}
_SEMANTIC_WEIGHT = 0.70
_OVERLAP_WEIGHT = 0.30
_CALIBRATED_MIN = 0.55
_CALIBRATED_MAX = 0.98


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


def _standardize_role(role_text: str) -> str:
    text = (role_text or "").strip()
    if not text:
        return ""
    text = _ROLE_NOISE_RE.sub("", text).strip()
    parts = [p.strip() for p in _ROLE_SPLIT_RE.split(text) if p.strip()]
    return parts[0] if parts else text


def _resume_text(user_id: int) -> Optional[str]:
    resume = (
        db.session.query(Resume).filter_by(user_id=user_id).one_or_none()
    )
    if resume is None:
        return None
    text = (resume.parsed_text or "").strip()
    return text or None


def _prepare_resume_text_for_embedding(text: str) -> str:
    """Compact resume text so embeddings focus on strongest signals."""
    cleaned = " ".join((text or "").split())
    terms = sorted(_extract_terms(cleaned))
    if not terms:
        return cleaned
    top_terms = ", ".join(terms[:80])
    return f"{cleaned}\n\nKey skills and terms: {top_terms}"


def _compute_resume_vector(user_id: int, text: str) -> List[float]:
    """Return resume vector and refresh ResumeEmbedding cache."""
    embedding_text = _prepare_resume_text_for_embedding(text)
    upsert_resume_embedding(
        db.session, user_id, embedding_text, source="resume"
    )
    db.session.flush()
    emb = db.session.get(ResumeEmbedding, user_id)
    return list(emb.embedding)


def _job_recency_key(job: Job) -> tuple[date, datetime]:
    posted = job.posted_at or date.min
    created = job.created_at or datetime.min
    return (posted, created)


def _filter_candidate_jobs(roles: List[str], companies: List[str]) -> List[Job]:
    normalized_roles = {
        _standardize_role(r).lower() for r in roles if isinstance(r, str) and r.strip()
    }
    if not normalized_roles:
        return []
    q = db.session.query(Job)

    company_filters = [
        func.lower(Job.company).contains(c.lower()) for c in companies if c
    ]
    if company_filters:
        q = q.filter(or_(*company_filters))
    jobs = q.all()
    return [
        job
        for job in jobs
        if _standardize_role(job.role).lower() in normalized_roles
    ]


def _ensure_job_vector(job: Job) -> List[float]:
    emb = db.session.get(JobEmbedding, job.id)
    if emb is None:
        upsert_job_embedding(
            db.session,
            job.id,
            _prepare_job_text_for_embedding(job),
        )
        db.session.flush()
        emb = db.session.get(JobEmbedding, job.id)
    return list(emb.embedding)


def _prepare_job_text_for_embedding(job: Job) -> str:
    parts = [job.role or "", job.company or "", job.description or ""]
    return " ".join(p.strip() for p in parts if p and p.strip())


def _extract_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for token in _TOKEN_RE.findall((text or "").lower()):
        if len(token) < 2 or token in _STOPWORDS:
            continue
        terms.add(token)
    return terms


def _skill_overlap_score(resume_text: str, job: Job) -> float:
    resume_terms = _extract_terms(resume_text)
    if not resume_terms:
        return 0.0
    job_terms = _extract_terms(_prepare_job_text_for_embedding(job))
    if not job_terms:
        return 0.0
    overlap = len(resume_terms & job_terms)
    # Recall-style overlap: how much of candidate profile appears in the job.
    return overlap / len(resume_terms)


def _hybrid_score(cosine: float, overlap: float) -> float:
    semantic = max(-1.0, min(1.0, cosine))
    semantic_01 = (semantic + 1.0) / 2.0
    score = (_SEMANTIC_WEIGHT * semantic_01) + (_OVERLAP_WEIGHT * overlap)
    return max(0.0, min(1.0, score))


def _calibrate_resume_scores(
    scored: List[tuple[Job, float]]
) -> List[tuple[Job, float]]:
    """Map raw hybrid scores into a user-friendly percentage band.

    Calibration is monotonic, so ranking order is preserved.
    """
    if not scored:
        return scored

    raws = [score for _job, score in scored]
    lo = min(raws)
    hi = max(raws)
    spread = hi - lo

    if spread <= 1e-8:
        # Degenerate case: equal raw scores. Use a gentle rank decay so
        # list order remains stable and scores do not all display identical.
        out: List[tuple[Job, float]] = []
        step = min(0.01, (_CALIBRATED_MAX - _CALIBRATED_MIN) / max(len(scored), 1))
        for idx, (job, _raw) in enumerate(scored):
            calibrated = max(_CALIBRATED_MIN, _CALIBRATED_MAX - (idx * step))
            out.append((job, calibrated))
        return out

    out: List[tuple[Job, float]] = []
    for job, raw in scored:
        norm = (raw - lo) / spread
        calibrated = _CALIBRATED_MIN + (
            (_CALIBRATED_MAX - _CALIBRATED_MIN) * norm
        )
        out.append((job, max(0.0, min(1.0, calibrated))))
    return out


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
    resume_text = _resume_text(user_id)

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

    scored = []
    if resume_text is None:
        # No resume: do not use vector logic. Rank by recency.
        candidates.sort(key=_job_recency_key, reverse=True)
        scored = [(job, 1.0) for job in candidates]
    else:
        user_vec = _compute_resume_vector(user_id, resume_text)
        user_arr = np.asarray(user_vec, dtype=np.float32)
        user_norm = float(np.linalg.norm(user_arr))
        if user_norm == 0.0:
            db.session.commit()
            return []

        for job in candidates:
            job_vec = _ensure_job_vector(job)
            job_arr = np.asarray(job_vec, dtype=np.float32)
            job_norm = float(np.linalg.norm(job_arr))
            if job_norm == 0.0:
                continue
            cos = float(np.dot(user_arr, job_arr) / (user_norm * job_norm))
            overlap = _skill_overlap_score(resume_text, job)
            scored.append((job, _hybrid_score(cos, overlap)))
        scored.sort(key=lambda t: t[1], reverse=True)
        scored = _calibrate_resume_scores(scored)
        scored = [(job, score) for job, score in scored if score >= threshold]
        scored.sort(key=lambda t: _job_recency_key(t[0]), reverse=True)

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
        .order_by(
            Job.posted_at.desc(),
            Job.created_at.desc(),
            Recommendation.similarity_score.desc(),
            Recommendation.computed_at.desc(),
        )
        .all()
    )
    return [_to_dto(job, rec.similarity_score) for rec, job in rows]
