"""Test fixtures.

Requires a real Postgres reachable at DATABASE_URL (see README.md's
"Running tests" section) with migrations already applied — these are
integration tests against the real ORM/DB layer, not unit tests with a
mocked database, since the bugs worth guarding against here (stale
SQLAlchemy identity-map reads) only reproduce against a real session/DB
round-trip.

Uses dev auth bypass (CORE_DEV_AUTH_BYPASS=true) instead of mocking
firebase_admin, and a fake in-memory object store instead of a real MinIO,
so the only external dependency is Postgres itself.
"""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

os.environ["CORE_DEV_AUTH_BYPASS"] = "true"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _fake_storage(monkeypatch):
    """Replaces app.services.storage's boto3-backed functions with an
    in-memory dict, so tests don't need a real S3/MinIO endpoint."""
    from app.services import storage

    fake_objects: dict[str, bytes] = {}

    monkeypatch.setattr(storage, "ensure_bucket", lambda: None)
    monkeypatch.setattr(
        storage, "presigned_upload_url", lambda key: f"http://fake-s3/{key}"
    )
    monkeypatch.setattr(
        storage, "presigned_download_url", lambda key: f"http://fake-s3/{key}"
    )
    monkeypatch.setattr(
        storage, "delete_object", lambda key: fake_objects.pop(key, None)
    )
    monkeypatch.setattr(
        storage,
        "download_to_path",
        lambda key, dest: open(dest, "wb").write(fake_objects.get(key, b"fake-audio")),
    )
    return fake_objects


@pytest.fixture(autouse=True)
async def _clean_db():
    """Truncates all tables before each test, so tests don't interfere with
    each other (and can reuse fixed ids like "s1" without collisions).

    Also disposes app.db.engine's connection pool after each test: anyio's
    default test runner opens a fresh event loop per test function, but
    engine (and its pooled asyncpg connections) is created once at import
    time bound to whichever loop was active then — connections then fail
    cross-loop on the next test with "attached to a different loop" /
    "Event loop is closed". Disposing forces a new pool (bound to the
    current loop) to be created lazily on next use.
    """
    from app.db import engine
    from app.models.user import User

    async with engine.begin() as conn:
        await conn.execute(delete(User))
    yield
    await engine.dispose()


@pytest.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def auth_headers(uid: str = "test-uid") -> dict:
    return {"Authorization": f"Bearer {uid}"}
