"""Integration tests against a real Postgres (see README.md for how to
point DATABASE_URL at a throwaway instance) — these specifically guard
against the identity-map staleness bugs found while manually verifying
this API (replace_transcript / replace_note returning stale data after a
raw delete()+add() instead of mutating through the ORM relationship).
"""

from __future__ import annotations

import pytest

from .conftest import auth_headers


@pytest.mark.anyio
async def test_create_and_get_session(client):
    resp = await client.post(
        "/sessions",
        json={
            "id": "s1",
            "title": "Kajian Sabar",
            "createdAt": "2026-07-22T10:00:00Z",
            "localeId": "id_ID",
        },
        headers=auth_headers(),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Kajian Sabar"
    assert body["transcript"] == []
    assert body["note"] is None
    assert body["hasAudio"] is False

    resp = await client.get("/sessions", headers=auth_headers())
    assert resp.status_code == 200
    assert [s["id"] for s in resp.json()] == ["s1"]


@pytest.mark.anyio
async def test_replace_transcript_reflects_immediately(client):
    await client.post(
        "/sessions",
        json={"id": "s2", "title": "T", "createdAt": "2026-07-22T10:00:00Z"},
        headers=auth_headers(),
    )
    resp = await client.put(
        "/sessions/s2/transcript",
        json={
            "segments": [
                {"id": "0", "text": "Halo dunia", "startMs": 0, "endMs": 1000},
            ]
        },
        headers=auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    # Regression guard: this used to come back as [] due to a stale
    # SQLAlchemy identity-map read after a raw delete()+add().
    assert len(body["transcript"]) == 1
    assert body["transcript"][0]["text"] == "Halo dunia"
    assert isinstance(body["transcript"][0]["id"], str)

    # A second replace should fully swap the segments, not append.
    resp = await client.put(
        "/sessions/s2/transcript",
        json={"segments": [{"id": "0", "text": "Second pass", "startMs": 0, "endMs": 500}]},
        headers=auth_headers(),
    )
    body = resp.json()
    assert len(body["transcript"]) == 1
    assert body["transcript"][0]["text"] == "Second pass"


@pytest.mark.anyio
async def test_replace_note_reflects_immediately(client):
    await client.post(
        "/sessions",
        json={"id": "s3", "title": "T", "createdAt": "2026-07-22T10:00:00Z"},
        headers=auth_headers(),
    )
    resp = await client.put(
        "/sessions/s3/note",
        json={
            "summary": "Ringkasan",
            "keyPoints": ["a", "b"],
            "topics": ["Sabar"],
            "references": [{"type": "quran", "citation": "Al-Baqarah: 153"}],
            "actionItems": ["x"],
        },
        headers=auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    # Regression guard: this used to come back as null due to the same
    # stale-identity-map pattern as the transcript bug above.
    assert body["note"] is not None
    assert body["note"]["summary"] == "Ringkasan"
    assert body["note"]["keyPoints"] == ["a", "b"]
    assert len(body["note"]["references"]) == 1
    assert body["note"]["references"][0]["citation"] == "Al-Baqarah: 153"

    # Replacing again should fully swap, not accumulate.
    resp = await client.put(
        "/sessions/s3/note",
        json={"summary": "Ringkasan v2"},
        headers=auth_headers(),
    )
    body = resp.json()
    assert body["note"]["summary"] == "Ringkasan v2"
    assert body["note"]["keyPoints"] == []
    assert body["note"]["references"] == []


@pytest.mark.anyio
async def test_audio_upload_and_delete_lifecycle(client, _fake_storage):
    await client.post(
        "/sessions",
        json={"id": "s4", "title": "T", "createdAt": "2026-07-22T10:00:00Z"},
        headers=auth_headers(),
    )
    resp = await client.post(
        "/sessions/s4/audio-upload-url", headers=auth_headers()
    )
    assert resp.status_code == 200
    object_key = resp.json()["objectKey"]
    _fake_storage[object_key] = b"fake-audio-bytes"

    resp = await client.post("/sessions/s4/audio-confirm", headers=auth_headers())
    assert resp.json()["hasAudio"] is True

    resp = await client.get("/sessions/s4/audio-url", headers=auth_headers())
    assert resp.status_code == 200

    resp = await client.delete("/sessions/s4", headers=auth_headers())
    assert resp.status_code == 204
    assert object_key not in _fake_storage  # deleted alongside the session


@pytest.mark.anyio
async def test_session_scoped_to_owner(client):
    await client.post(
        "/sessions",
        json={"id": "s5", "title": "Owner's", "createdAt": "2026-07-22T10:00:00Z"},
        headers=auth_headers("user-a"),
    )
    resp = await client.get("/sessions", headers=auth_headers("user-b"))
    assert resp.json() == []

    resp = await client.get("/sessions/s5/audio-url", headers=auth_headers("user-b"))
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_get_me_auto_provisions_user(client):
    resp = await client.get("/me", headers=auth_headers("new-user"))
    assert resp.status_code == 200
    assert resp.json()["isAdmin"] is False


@pytest.mark.anyio
async def test_missing_auth_header_returns_401(client):
    resp = await client.get("/sessions")
    assert resp.status_code == 401


@pytest.mark.anyio
async def test_admin_endpoints_require_admin_flag(client):
    resp = await client.get("/admin/stats", headers=auth_headers("regular-user"))
    assert resp.status_code == 403
