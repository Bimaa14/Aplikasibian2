"""Isolated tests for the one-time demo administrator setup route."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

import server
from routers import setup_demo


class FakeUsers:
    def __init__(self, duplicate: bool = False):
        self.duplicate = duplicate
        self.documents: list[dict] = []

    async def insert_one(self, document: dict):
        if self.duplicate:
            raise DuplicateKeyError("duplicate key")
        self.documents.append(document)


class FakeDatabase:
    def __init__(self, duplicate: bool = False):
        self.users = FakeUsers(duplicate)


@pytest.fixture
def setup_key(monkeypatch):
    monkeypatch.setenv("DEMO_SETUP_KEY", "a" * 32)


@pytest.mark.asyncio
async def test_setup_creates_fixed_admin_only_once(monkeypatch, setup_key):
    fake_db = FakeDatabase()
    monkeypatch.setattr(setup_demo, "db", fake_db)

    response = await setup_demo.setup_demo("a" * 32, "password-demo-aman")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "set-cookie" not in response.headers
    assert len(fake_db.users.documents) == 1
    account = fake_db.users.documents[0]
    assert account["_id"] == "demo-admin"
    assert account["username"] == "demo-admin"
    assert account["role"] == "admin"
    assert account["password_hash"] != "password-demo-aman"
    assert "password-demo-aman" not in response.body.decode()


@pytest.mark.asyncio
async def test_setup_never_overwrites_existing_account(monkeypatch, setup_key):
    fake_db = FakeDatabase(duplicate=True)
    monkeypatch.setattr(setup_demo, "db", fake_db)

    response = await setup_demo.setup_demo("a" * 32, "password-demo-aman")

    assert response.status_code == 200
    assert not fake_db.users.documents
    assert "sudah ada" in response.body.decode()


@pytest.mark.asyncio
async def test_setup_rejects_bad_secret_without_writing(monkeypatch, setup_key):
    fake_db = FakeDatabase()
    monkeypatch.setattr(setup_demo, "db", fake_db)

    with pytest.raises(HTTPException) as error:
        await setup_demo.setup_demo("wrong", "password-demo-aman")

    assert error.value.status_code == 403
    assert not fake_db.users.documents


@pytest.mark.asyncio
async def test_setup_is_disabled_without_valid_key(monkeypatch):
    monkeypatch.delenv("DEMO_SETUP_KEY", raising=False)

    with pytest.raises(HTTPException) as error:
        await setup_demo.setup_demo_form()

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_setup_rejects_password_over_bcrypt_limit(monkeypatch, setup_key):
    fake_db = FakeDatabase()
    monkeypatch.setattr(setup_demo, "db", fake_db)

    response = await setup_demo.setup_demo("a" * 32, "a" * 73)

    assert response.status_code == 200
    assert not fake_db.users.documents
    assert "maksimal 72 byte" in response.body.decode()


def test_setup_form_origin_passes_strict_csrf_middleware(monkeypatch, setup_key):
    backend_origin = "https://backend.example"
    fake_db = FakeDatabase()
    monkeypatch.setattr(setup_demo, "db", fake_db)
    monkeypatch.setattr(server, "COOKIE_SAMESITE", "none")
    monkeypatch.setattr(server, "CORS_ORIGINS", [backend_origin])

    # Simulate a reverse proxy where the app-visible origin differs from the public origin.
    client = TestClient(server.app, base_url="http://internal-service")
    form = client.get("/api/setup-demo")

    assert form.status_code == 200
    assert form.headers["referrer-policy"] == "same-origin"

    accepted = client.post(
        "/api/setup-demo",
        data={"secret": "a" * 32, "password": "password-demo-aman"},
        headers={"Origin": backend_origin},
    )
    assert accepted.status_code == 200
    assert len(fake_db.users.documents) == 1

    for origin in ("null", "https://untrusted.example"):
        rejected = client.post("/api/ordinary-mutation", headers={"Origin": origin})
        assert rejected.status_code == 403
        assert rejected.text == "Untrusted request origin"
