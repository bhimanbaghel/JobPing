"""
Tests for POST /api/auth/register

Run from backend/:  pytest tests/test_auth_register.py -v

Uses SQLite in-memory — doesn't touch your Render PostgreSQL.
"""

import pytest
from app import create_app
from app.models import db, User


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="test@example.com", password="SecurePass99"):
    return client.post("/api/auth/register", json={
        "email": email, "password": password,
    })


# ── Happy path ──────────────────────────────────────────────────────

class TestRegisterSuccess:
    def test_returns_201_with_token(self, client):
        resp = register(client)
        assert resp.status_code == 201
        data = resp.get_json()
        assert "access_token" in data
        assert data["user"]["email"] == "test@example.com"
        assert "password" not in data["user"]

    def test_stores_user_in_db(self, client, app):
        register(client)
        with app.app_context():
            user = User.query.filter_by(email="test@example.com").first()
            assert user is not None
            assert user.password_hash != "SecurePass99"
            assert user.password_hash.startswith(("scrypt:", "pbkdf2:"))

    def test_email_stored_lowercase(self, client, app):
        register(client, email="Test@EXAMPLE.com")
        with app.app_context():
            assert User.query.filter_by(email="test@example.com").first() is not None


# ── Missing fields ──────────────────────────────────────────────────

class TestRegisterMissingFields:
    def test_missing_email(self, client):
        resp = client.post("/api/auth/register", json={"password": "ValidPass1"})
        assert resp.status_code == 400
        assert "email" in resp.get_json()["error"]

    def test_missing_password(self, client):
        resp = client.post("/api/auth/register", json={"email": "a@b.com"})
        assert resp.status_code == 400
        assert "password" in resp.get_json()["error"]

    def test_empty_body(self, client):
        resp = client.post("/api/auth/register", data="not json", content_type="text/plain")
        assert resp.status_code == 400


# ── Email validation ────────────────────────────────────────────────

class TestRegisterEmailValidation:
    @pytest.mark.parametrize("bad_email", [
        "notanemail", "@missing.local", "no-at-sign.com", "spaces in@email.com"
    ])
    def test_rejects_invalid_email(self, client, bad_email):
        resp = register(client, email=bad_email)
        assert resp.status_code == 400


# ── Email uniqueness ────────────────────────────────────────────────

class TestRegisterDuplicateEmail:
    def test_duplicate_email_returns_409(self, client):
        register(client, email="dupe@test.com")
        resp = register(client, email="dupe@test.com", password="AnotherPass1")
        assert resp.status_code == 409
        assert "already exists" in resp.get_json()["error"]

    def test_duplicate_email_case_insensitive(self, client):
        register(client, email="dupe@test.com")
        resp = register(client, email="DUPE@test.com", password="AnotherPass1")
        assert resp.status_code == 409


# ── NIST SP 800-63B password rules ──────────────────────────────────

class TestRegisterPasswordPolicy:
    def test_rejects_short_password(self, client):
        resp = register(client, password="Ab3defg")
        assert resp.status_code == 400
        assert "8 characters" in resp.get_json()["error"]

    def test_rejects_common_password(self, client):
        resp = register(client, password="password123")
        assert resp.status_code == 400
        assert "common" in resp.get_json()["error"].lower()

    def test_rejects_password_matching_email_username(self, client):
        resp = register(client, email="lakshay@pitt.edu", password="lakshay")
        assert resp.status_code == 400

    def test_accepts_long_passphrase(self, client):
        resp = register(client, password="correct horse battery staple is great")
        assert resp.status_code == 201

    def test_rejects_over_128_chars(self, client):
        resp = register(client, password="a" * 129)
        assert resp.status_code == 400

    def test_rejects_repeating_single_char(self, client):
        resp = register(client, password="aaaaaaaa")
        assert resp.status_code == 400
        assert "repeating" in resp.get_json()["error"].lower()

    def test_no_composition_rules_required(self, client):
        """NIST 800-63B: no forced uppercase/special chars."""
        resp = register(client, password="avocadotoast")
        assert resp.status_code == 201
