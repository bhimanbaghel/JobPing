"""Tests for GET /api/auth/me (email from users table)."""

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


def register_and_token(client, email="me@example.com", password="correct horse battery staple is great"):
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201
    return r.get_json()["access_token"]


class TestAuthMe:
    def test_returns_email_from_db(self, client, app):
        token = register_and_token(client)
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        data = r.get_json()
        assert data["email"] == "me@example.com"
        with app.app_context():
            u = User.query.filter_by(email="me@example.com").first()
            assert data["id"] == u.id

    def test_401_without_token(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401
