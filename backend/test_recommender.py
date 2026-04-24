"""Tests for the recommendation feature.

Covers:
  - FR6.1   minimum input (at least one preferred role)
  - FR6.2   matching uses preferences and resume content
  - FR6.3   no-resume mode uses lexical role matching + recency ordering
  - FR6.4   recommendations are sorted by similarity (desc)
  - Role phrase match gates inclusion; similarity ranks results
  - Filter by role and company
  - Persistence in the recommendations table (Table 3)
  - REST endpoints under /api/jobs/

Runs against in-memory SQLite (TestingConfig) and the deterministic
hashing embedding backend so the suite is fast and offline.
"""
import os

os.environ.setdefault("EMBEDDING_BACKEND", "hashing")

import pytest
from datetime import date
from werkzeug.security import generate_password_hash

from app import create_app
from app.models import (
    Job,
    JobEmbedding,
    Recommendation,
    Resume,
    ResumeEmbedding,
    User,
    UserPreference,
    db,
)
from app.services.recommender import (
    MissingRolePreferences,
    SIMILARITY_THRESHOLD,
    get_existing_recommendations,
    recommend_for_user,
)


# ───────────────────────────── fixtures ─────────────────────────────────────
@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def make_user(email: str = "u@u.com", password: str = "TestPass-1234567890!"):
    user = User(email=email, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.commit()
    return user, password


def make_pref(user_id, *, roles, companies=None, locations=None):
    pref = UserPreference(
        user_id=user_id,
        roles=list(roles),
        companies=list(companies or []),
        locations=list(locations or []),
    )
    db.session.add(pref)
    db.session.commit()
    return pref


def make_job(role, company, description, **extra):
    job = Job(role=role, company=company, description=description, **extra)
    db.session.add(job)
    db.session.commit()
    return job


def login(client, email, password):
    resp = client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.get_json()
    return {"Authorization": f"Bearer {resp.get_json()['access_token']}"}


# ───────────────────────────── service tests ────────────────────────────────
class TestServiceLayer:
    def test_fr6_1_missing_role_preferences_raises(self, app):
        user, _ = make_user()
        with pytest.raises(MissingRolePreferences):
            recommend_for_user(user.id)

    def test_fr6_1_empty_role_list_raises(self, app):
        user, _ = make_user()
        make_pref(user.id, roles=[], companies=["Acme"])
        with pytest.raises(MissingRolePreferences):
            recommend_for_user(user.id)

    def test_fr6_3_preference_only_does_not_require_resume_embeddings(self, app):
        user, _ = make_user()
        make_pref(user.id, roles=["Backend Engineer"], companies=["Acme"])
        make_job(
            "Backend Engineer",
            "Acme Corp",
            "Looking for roles: Backend Engineer. Preferred companies: Acme.",
        )
        recs = recommend_for_user(user.id)
        assert len(recs) == 1
        emb = db.session.get(ResumeEmbedding, user.id)
        assert emb is None

    def test_resume_overrides_preferences_when_present(self, app):
        user, _ = make_user()
        make_pref(user.id, roles=["Backend Engineer"], companies=["Acme"])
        make_job(
            "Backend Engineer",
            "Acme Corp",
            "python flask postgres backend api",
        )
        db.session.add(
            Resume(user_id=user.id, parsed_text="python flask postgres backend api")
        )
        db.session.commit()
        recs = recommend_for_user(user.id)
        assert len(recs) == 1
        assert recs[0].similarity_score >= 0.99
        emb = db.session.get(ResumeEmbedding, user.id)
        assert emb.source == "resume"

    def test_role_phrase_match_includes_low_scoring_jobs(self, app):
        user, _ = make_user()
        make_pref(user.id, roles=["Backend Engineer"])
        make_job(
            "Backend Engineer",
            "Acme",
            "python flask postgres backend api",
        )
        make_job(
            "Backend Engineer",
            "Initech",
            "completely unrelated text about cooking and cats",
        )
        db.session.add(
            Resume(user_id=user.id, parsed_text="python flask postgres backend api")
        )
        db.session.commit()
        recs = recommend_for_user(user.id)
        assert len(recs) == 2
        assert {r.company for r in recs} == {"Acme", "Initech"}
        assert recs[0].similarity_score >= recs[1].similarity_score

    def test_fr6_4_results_sorted_by_similarity_desc(self, app):
        user, _ = make_user()
        make_pref(user.id, roles=["Engineer"])
        make_job("Engineer", "A", "python flask postgres backend api")
        make_job("Engineer", "B", "python flask postgres backend service")
        make_job("Engineer", "C", "python flask")
        db.session.add(
            Resume(user_id=user.id, parsed_text="python flask postgres backend api")
        )
        db.session.commit()
        recs = recommend_for_user(user.id, threshold=0.0)
        scores = [r.similarity_score for r in recs]
        assert scores == sorted(scores, reverse=True)

    def test_filter_by_role_applies(self, app):
        user, _ = make_user()
        make_pref(user.id, roles=["Backend Engineer"])
        make_job("Backend Engineer", "A", "python")
        make_job("Frontend Designer", "A", "python")
        db.session.add(Resume(user_id=user.id, parsed_text="python"))
        db.session.commit()
        recs = recommend_for_user(user.id, threshold=0.0)
        assert {r.role for r in recs} == {"Backend Engineer"}

    def test_standardized_role_match_is_exact(self, app):
        user, _ = make_user()
        make_pref(user.id, roles=["Software Engineer"])
        make_job("Software Engineer, Platform", "A", "python")
        make_job("Staff Software Engineer - Infra", "B", "python")
        db.session.add(Resume(user_id=user.id, parsed_text="python"))
        db.session.commit()
        recs = recommend_for_user(user.id, threshold=0.0)
        assert {r.company for r in recs} == {"A"}

    def test_no_resume_results_sorted_by_posted_date_desc(self, app):
        user, _ = make_user()
        make_pref(user.id, roles=["Engineer"])
        make_job(
            "Engineer",
            "OldCo",
            "python backend",
            posted_at=date(2026, 1, 1),
        )
        make_job(
            "Engineer",
            "NewCo",
            "python backend",
            posted_at=date(2026, 3, 1),
        )
        recs = recommend_for_user(user.id)
        assert [r.company for r in recs] == ["NewCo", "OldCo"]
        assert [r.similarity_score for r in recs] == [1.0, 1.0]

    def test_filter_by_company_applies_when_set(self, app):
        user, _ = make_user()
        make_pref(user.id, roles=["Engineer"], companies=["Acme"])
        make_job("Engineer", "Acme Corp", "python")
        make_job("Engineer", "Globex", "python")
        db.session.add(Resume(user_id=user.id, parsed_text="python"))
        db.session.commit()
        recs = recommend_for_user(user.id, threshold=0.0)
        assert {r.company for r in recs} == {"Acme Corp"}

    def test_empty_companies_means_no_company_filter(self, app):
        user, _ = make_user()
        make_pref(user.id, roles=["Engineer"], companies=[])
        make_job("Engineer", "Acme Corp", "python")
        make_job("Engineer", "Globex", "python")
        db.session.add(Resume(user_id=user.id, parsed_text="python"))
        db.session.commit()
        recs = recommend_for_user(user.id, threshold=0.0)
        assert {r.company for r in recs} == {"Acme Corp", "Globex"}

    def test_persists_into_recommendations_table(self, app):
        user, _ = make_user()
        make_pref(user.id, roles=["Engineer"])
        make_job("Engineer", "Acme", "python")
        db.session.add(Resume(user_id=user.id, parsed_text="python"))
        db.session.commit()
        recommend_for_user(user.id, threshold=0.0)
        rows = (
            db.session.query(Recommendation).filter_by(user_id=user.id).all()
        )
        assert len(rows) == 1
        assert rows[0].similarity_score >= SIMILARITY_THRESHOLD

    def test_recompute_replaces_old_rows(self, app):
        user, _ = make_user()
        make_pref(user.id, roles=["Engineer"])
        a = make_job("Engineer", "Acme", "python")
        db.session.add(Resume(user_id=user.id, parsed_text="python"))
        db.session.commit()
        recommend_for_user(user.id, threshold=0.0)

        # delete the only matching job, recompute -> no rows
        db.session.delete(a)
        db.session.commit()
        recs = recommend_for_user(user.id, threshold=0.0)
        assert recs == []
        assert (
            db.session.query(Recommendation).filter_by(user_id=user.id).count()
            == 0
        )

    def test_caches_job_embeddings(self, app):
        user, _ = make_user()
        make_pref(user.id, roles=["Engineer"])
        job = make_job("Engineer", "Acme", "python flask")
        db.session.add(Resume(user_id=user.id, parsed_text="python flask"))
        db.session.commit()
        recommend_for_user(user.id)
        emb = db.session.get(JobEmbedding, job.id)
        assert emb is not None
        assert len(emb.embedding) == 384

    def test_get_existing_returns_sorted_without_recomputing(self, app):
        user, _ = make_user()
        make_pref(user.id, roles=["Engineer"])
        make_job("Engineer", "A", "python flask postgres")
        make_job("Engineer", "B", "python flask")
        db.session.add(Resume(user_id=user.id, parsed_text="python flask postgres"))
        db.session.commit()
        recommend_for_user(user.id, threshold=0.0)
        rows = get_existing_recommendations(user.id)
        scores = [r.similarity_score for r in rows]
        assert scores == sorted(scores, reverse=True)


# ───────────────────────────── api tests ────────────────────────────────────
class TestRecommendationsApi:
    def test_requires_auth(self, client):
        assert client.get("/api/jobs/recommendations").status_code == 401
        assert (
            client.post("/api/jobs/recommendations/recompute").status_code == 401
        )
        assert client.get("/api/jobs/1").status_code == 401

    def test_returns_recommendations_for_authed_user(self, client, app):
        user, pwd = make_user()
        make_pref(user.id, roles=["Backend Engineer"], companies=["Acme"])
        make_job(
            "Backend Engineer",
            "Acme Corp",
            "python flask postgres backend api",
        )
        db.session.add(
            Resume(user_id=user.id, parsed_text="python flask postgres backend api")
        )
        db.session.commit()
        headers = login(client, user.email, pwd)
        resp = client.get("/api/jobs/recommendations", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 1
        item = body["items"][0]
        assert item["company"] == "Acme Corp"
        assert item["similarity_score"] >= SIMILARITY_THRESHOLD
        assert item["location"] == {
            "city": None,
            "state": None,
            "country": None,
        }

    def test_fr6_1_violation_returns_400_with_code(self, client, app):
        user, pwd = make_user()
        headers = login(client, user.email, pwd)
        resp = client.get("/api/jobs/recommendations", headers=headers)
        assert resp.status_code == 400
        body = resp.get_json()
        assert body["code"] == "missing_role_preferences"

    def test_recompute_forces_recomputation(self, client, app):
        user, pwd = make_user()
        make_pref(user.id, roles=["Engineer"])
        make_job("Engineer", "Acme", "python flask")
        db.session.add(Resume(user_id=user.id, parsed_text="python flask"))
        db.session.commit()
        headers = login(client, user.email, pwd)
        first = client.get("/api/jobs/recommendations", headers=headers)
        assert first.status_code == 200
        recompute = client.post(
            "/api/jobs/recommendations/recompute", headers=headers
        )
        assert recompute.status_code == 200
        assert recompute.get_json()["count"] == first.get_json()["count"]

    def test_get_job_returns_full_detail(self, client, app):
        user, pwd = make_user()
        job = make_job(
            "Backend",
            "Acme",
            "Job description.",
            link="https://acme.example.com/jobs/1",
            city="Pittsburgh",
            state="PA",
            country="USA",
            salary_usd=150000,
        )
        headers = login(client, user.email, pwd)
        resp = client.get(f"/api/jobs/{job.id}", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["company"] == "Acme"
        assert body["link"] == "https://acme.example.com/jobs/1"
        assert body["location"]["city"] == "Pittsburgh"
        assert body["salary_usd"] == 150000.0

    def test_get_job_404_when_missing(self, client, app):
        user, pwd = make_user()
        headers = login(client, user.email, pwd)
        resp = client.get("/api/jobs/9999", headers=headers)
        assert resp.status_code == 404
