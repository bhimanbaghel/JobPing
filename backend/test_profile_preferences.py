"""Tests for profile preference onboarding endpoints."""

import io

import pytest

from app import create_app
from app.models import Job, Recommendation, Resume, UserPreference, db


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


def register_and_token(
    client, email="pref@example.com", password="correct horse battery staple is great"
):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201
    return r.get_json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_preferences_status_false_for_new_user(client):
    token = register_and_token(client)
    r = client.get("/api/profile/preferences/status", headers=auth_headers(token))
    assert r.status_code == 200
    body = r.get_json()
    assert body["has_preferences"] is False
    assert body["has_resume"] is False
    assert body["roles"] == []
    assert body["companies"] == []


def test_save_preferences_requires_roles(client):
    token = register_and_token(client)
    r = client.post("/api/profile/preferences", headers=auth_headers(token), data={})
    assert r.status_code == 400
    assert "role" in r.get_json()["error"].lower()


def test_save_preferences_upserts_roles(client, app):
    token = register_and_token(client)
    r = client.post(
        "/api/profile/preferences",
        headers=auth_headers(token),
        data={"roles": ["Backend Engineer", "Data Engineer"]},
    )
    assert r.status_code == 200
    with app.app_context():
        pref = db.session.query(UserPreference).one()
        assert pref.roles == ["Backend Engineer", "Data Engineer"]


def test_save_preferences_with_optional_companies(client, app):
    token = register_and_token(client)
    r = client.post(
        "/api/profile/preferences",
        headers=auth_headers(token),
        data={"roles": ["Backend Engineer"], "companies": ["Acme", "Globex"]},
    )
    assert r.status_code == 200
    with app.app_context():
        pref = db.session.query(UserPreference).one()
        assert pref.roles == ["Backend Engineer"]
        assert pref.companies == ["Acme", "Globex"]


def test_save_preferences_rejects_non_pdf_resume(client):
    token = register_and_token(client)
    data = {
        "roles": ["Backend Engineer"],
        "resume": (io.BytesIO(b"hello"), "resume.txt"),
    }
    r = client.post(
        "/api/profile/preferences",
        headers=auth_headers(token),
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "pdf" in r.get_json()["error"].lower()


def test_save_preferences_rejects_too_large_resume(client):
    token = register_and_token(client)
    data = {
        "roles": ["Backend Engineer"],
        "resume": (io.BytesIO(b"x" * (5 * 1024 * 1024 + 1)), "resume.pdf"),
    }
    r = client.post(
        "/api/profile/preferences",
        headers=auth_headers(token),
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "smaller than 5mb" in r.get_json()["error"].lower()


def test_save_preferences_stores_parsed_resume_text(client, app, monkeypatch):
    token = register_and_token(client)

    def _fake_extract(_file_bytes):
        return "python flask postgres"

    monkeypatch.setattr(
        "app.blueprints.profile.routes.extract_text_from_pdf_bytes",
        _fake_extract,
    )

    data = {
        "roles": ["Backend Engineer"],
        "resume": (io.BytesIO(b"%PDF-1.4 fake"), "resume.pdf"),
    }
    r = client.post(
        "/api/profile/preferences",
        headers=auth_headers(token),
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 200

    with app.app_context():
        resume = db.session.query(Resume).one()
        assert resume.parsed_text == "python flask postgres"

    status = client.get("/api/profile/preferences/status", headers=auth_headers(token))
    assert status.status_code == 200
    body = status.get_json()
    assert body["has_preferences"] is True
    assert body["has_resume"] is True


def test_role_options_returns_standardized_roles(client, app):
    token = register_and_token(client)
    with app.app_context():
        db.session.add_all(
            [
                Job(
                    role="Software Engineer (Backend) - Remote",
                    company="acme",
                    description="d1",
                ),
                Job(
                    role="Software Engineer, Platform",
                    company="globex",
                    description="d2",
                ),
                Job(
                    role="Data Scientist | ML",
                    company="initech",
                    description="d3",
                ),
            ]
        )
        db.session.commit()

    r = client.get(
        "/api/profile/preferences/role-options", headers=auth_headers(token)
    )
    assert r.status_code == 200
    roles = r.get_json()["roles"]
    assert "Software Engineer" in roles
    assert "Data Scientist" in roles


def test_company_options_returns_standardized_companies(client, app):
    token = register_and_token(client)
    with app.app_context():
        db.session.add_all(
            [
                Job(
                    role="Software Engineer",
                    company=" Acme Corp ",
                    description="d1",
                ),
                Job(
                    role="Data Engineer",
                    company="Globex",
                    description="d2",
                ),
            ]
        )
        db.session.commit()

    r = client.get(
        "/api/profile/preferences/company-options", headers=auth_headers(token)
    )
    assert r.status_code == 200
    companies = r.get_json()["companies"]
    assert "Acme Corp" in companies
    assert "Globex" in companies


def test_save_preferences_can_be_modified_after_first_save(client, app):
    """Re-saving preferences must succeed — there is no lock blocking edits."""
    token = register_and_token(client)

    r1 = client.post(
        "/api/profile/preferences",
        headers=auth_headers(token),
        data={"roles": ["Backend Engineer"]},
    )
    assert r1.status_code == 200

    r2 = client.post(
        "/api/profile/preferences",
        headers=auth_headers(token),
        data={"roles": ["Data Engineer"]},
    )
    assert r2.status_code == 200

    with app.app_context():
        pref = db.session.query(UserPreference).one()
        assert pref.roles == ["Data Engineer"]


def test_save_preferences_invalidates_cached_recommendations(client, app, monkeypatch):
    """Saving preferences must wipe cached `recommendations` rows so the next
    GET recomputes against the new resume / roles / companies."""
    token = register_and_token(client)

    def _fake_extract(_file_bytes):
        return "python flask postgres"

    monkeypatch.setattr(
        "app.blueprints.profile.routes.extract_text_from_pdf_bytes",
        _fake_extract,
    )

    # First save: creates user + preferences + resume.
    r = client.post(
        "/api/profile/preferences",
        headers=auth_headers(token),
        data={
            "roles": ["Backend Engineer"],
            "resume": (io.BytesIO(b"%PDF-1.4 fake"), "resume.pdf"),
        },
        content_type="multipart/form-data",
    )
    assert r.status_code == 200

    # Seed a cached recommendation row as if recommend_for_user had run.
    with app.app_context():
        pref = db.session.query(UserPreference).one()
        user_id = pref.user_id
        job = Job(role="Backend Engineer", company="Acme", description="d")
        db.session.add(job)
        db.session.flush()
        db.session.add(
            Recommendation(user_id=user_id, job_id=job.id, similarity_score=0.9)
        )
        db.session.commit()
        assert db.session.query(Recommendation).filter_by(user_id=user_id).count() == 1

    # Second save: even just role changes must invalidate the cache.
    r2 = client.post(
        "/api/profile/preferences",
        headers=auth_headers(token),
        data={"roles": ["Data Engineer"]},
    )
    assert r2.status_code == 200

    with app.app_context():
        assert db.session.query(Recommendation).filter_by(user_id=user_id).count() == 0


def test_preferences_status_does_not_expose_is_locked(client):
    """The deprecated is_locked flag must not appear in the status payload."""
    token = register_and_token(client)
    r = client.get("/api/profile/preferences/status", headers=auth_headers(token))
    assert r.status_code == 200
    assert "is_locked" not in r.get_json()

