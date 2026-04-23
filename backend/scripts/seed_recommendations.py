"""Seed sample data for the recommendation feature.

Usage (from backend/):

    EMBEDDING_BACKEND=hashing \
    DATABASE_URL=sqlite:///app.db \
    python -m scripts.seed_recommendations

Inserts (or upserts):
  - one demo user (demo@jobping.test / DemoPass-1234567890!)
  - their UserPreference (roles + companies)
  - their parsed Resume text
  - a handful of Job rows spanning the relevant + irrelevant cases

Then runs the recommender so you can hit GET /api/jobs/recommendations
and see real Table 3 rows immediately.
"""
from __future__ import annotations

import os
from datetime import date

from werkzeug.security import generate_password_hash

from app import create_app
from app.models import (
    Job,
    Resume,
    User,
    UserPreference,
    db,
)
from app.services.recommender import recommend_for_user

DEMO_EMAIL = "demo@jobping.test"
DEMO_PASSWORD = "DemoPass-1234567890!"


JOB_FIXTURES = [
    {
        "role": "Senior Backend Engineer",
        "company": "Acme Corp",
        "description": (
            "Build and operate Python services on AWS. Strong Flask, "
            "PostgreSQL, and REST API experience required. Comfortable "
            "with distributed systems, CI/CD, and on-call rotations."
        ),
        "link": "https://acme.example.com/jobs/backend-senior",
        "city": "Pittsburgh",
        "state": "PA",
        "country": "USA",
        "salary_usd": 175000,
        "posted_at": date(2026, 4, 1),
    },
    {
        "role": "Backend Engineer",
        "company": "Globex",
        "description": (
            "Python developer to extend our Flask + PostgreSQL platform. "
            "You will design REST APIs, work on background jobs, and "
            "collaborate with frontend on contracts."
        ),
        "link": "https://globex.example.com/careers/backend",
        "city": "Remote",
        "state": None,
        "country": "USA",
        "salary_usd": 145000,
        "posted_at": date(2026, 4, 10),
    },
    {
        "role": "Backend Engineer",
        "company": "Initech",
        "description": (
            "Cooking enthusiast wanted to write recipes for our internal "
            "cafeteria blog. Bonus points for cat photos."
        ),
        "link": "https://initech.example.com/jobs/blogger",
        "city": "Austin",
        "state": "TX",
        "country": "USA",
        "salary_usd": 65000,
        "posted_at": date(2026, 3, 20),
    },
    {
        "role": "Frontend Designer",
        "company": "Acme Corp",
        "description": "Figma, CSS, and visual systems for marketing pages.",
        "link": "https://acme.example.com/jobs/design-fe",
        "city": "Pittsburgh",
        "state": "PA",
        "country": "USA",
        "salary_usd": 130000,
        "posted_at": date(2026, 4, 5),
    },
]


def _upsert_demo_user() -> User:
    user = User.query.filter_by(email=DEMO_EMAIL).one_or_none()
    if user is not None:
        return user
    user = User(
        email=DEMO_EMAIL,
        password_hash=generate_password_hash(DEMO_PASSWORD),
    )
    db.session.add(user)
    db.session.commit()
    return user


def _upsert_preferences(user: User) -> None:
    pref = UserPreference.query.filter_by(user_id=user.id).one_or_none()
    if pref is None:
        pref = UserPreference(
            user_id=user.id,
            roles=["Backend Engineer"],
            companies=["Acme", "Globex"],
            locations=["Pittsburgh", "Remote"],
        )
        db.session.add(pref)
    else:
        pref.roles = ["Backend Engineer"]
        pref.companies = ["Acme", "Globex"]
        pref.locations = ["Pittsburgh", "Remote"]
    db.session.commit()


def _upsert_resume(user: User) -> None:
    text = (
        "Backend engineer with 5 years of Python, Flask, and PostgreSQL. "
        "Built REST APIs at scale on AWS and led migrations to "
        "containerized deployments. Comfortable with CI/CD and on-call."
    )
    resume = Resume.query.filter_by(user_id=user.id).one_or_none()
    if resume is None:
        db.session.add(Resume(user_id=user.id, parsed_text=text))
    else:
        resume.parsed_text = text
    db.session.commit()


def _upsert_jobs() -> None:
    for fx in JOB_FIXTURES:
        existing = (
            Job.query.filter_by(role=fx["role"], company=fx["company"]).first()
        )
        if existing is None:
            db.session.add(Job(**fx))
        else:
            for k, v in fx.items():
                setattr(existing, k, v)
    db.session.commit()


def seed() -> None:
    user = _upsert_demo_user()
    _upsert_preferences(user)
    _upsert_resume(user)
    _upsert_jobs()
    recs = recommend_for_user(user.id)
    print(f"Seeded {len(JOB_FIXTURES)} jobs for {DEMO_EMAIL}.")
    print(f"Computed {len(recs)} recommendations:")
    for r in recs:
        print(f"  {r.similarity_score:.3f}  {r.role} @ {r.company}")
    if not recs and os.environ.get("EMBEDDING_BACKEND", "sbert").lower() == "hashing":
        print()
        print(
            "Note: EMBEDDING_BACKEND=hashing is a deterministic test backend "
            "and is not semantic, so most fixtures fall below the 0.80 "
            "cutoff. Re-run with the default sbert backend (just unset "
            "EMBEDDING_BACKEND) to see meaningful recommendations."
        )
    print()
    print(f"Login with:\n  email:    {DEMO_EMAIL}\n  password: {DEMO_PASSWORD}")


def main() -> None:
    app = create_app()
    with app.app_context():
        db.create_all()
        seed()


if __name__ == "__main__":
    main()
