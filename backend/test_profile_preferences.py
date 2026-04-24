"""Tests for profile preference onboarding endpoints."""

import io

import pytest

from app import create_app
from app.models import Job, Resume, UserPreference, db


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


def test_lock_preferences_and_prevent_modification(client, app):
    token = register_and_token(client)
    # 1. Save and lock
    r = client.post(
        "/api/profile/preferences",
        headers=auth_headers(token),
        data={"roles": ["Backend Engineer"], "is_locked": "true"},
    )
    assert r.status_code == 200
    
    with app.app_context():
        pref = db.session.query(UserPreference).one()
        assert pref.roles == ["Backend Engineer"]
        assert pref.is_locked is True

    # 2. Try to modify again
    r_modify = client.post(
        "/api/profile/preferences",
        headers=auth_headers(token),
        data={"roles": ["Data Engineer"]},
    )
    assert r_modify.status_code == 403
    assert "locked" in r_modify.get_json()["error"].lower()

    # 3. Check status
    r_status = client.get("/api/profile/preferences/status", headers=auth_headers(token))
    assert r_status.status_code == 200
    body = r_status.get_json()
    assert body["is_locked"] is True

