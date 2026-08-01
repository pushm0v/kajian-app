"""The notes proxy's availability contract.

What matters here is the *distinction* the rest of the pipeline depends
on: NotesUnavailable means "degrade, keep the session" while anything
else means "this genuinely failed". routers/processing.py branches on
exactly that (see _run_summarization), so getting it wrong either strands
sessions in `error` or hides real breakage.
"""

import httpx
import pytest

from app import config
from app.services import notes


@pytest.fixture(autouse=True)
def _backend_url(monkeypatch):
    monkeypatch.setattr(config, "NOTES_BACKEND_URL", "http://notes:8080")
    monkeypatch.setattr(config, "NOTES_BACKEND_TOKEN", "")


def test_empty_transcript_returns_empty_notes_without_calling_out(monkeypatch):
    def boom(*a, **k):  # pragma: no cover - must not be reached
        raise AssertionError("should not have called the notes service")

    monkeypatch.setattr(httpx, "post", boom)
    out = notes.generate("   ", "Kajian")
    assert out["summary"] == ""
    assert out["keyPoints"] == []


def test_unset_url_is_unavailable_not_failure(monkeypatch):
    monkeypatch.setattr(config, "NOTES_BACKEND_URL", "")
    with pytest.raises(notes.NotesUnavailable, match="not configured"):
        notes.generate("ada isi", "Kajian")


def test_unreachable_service_is_unavailable(monkeypatch):
    def refuse(*a, **k):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", refuse)
    with pytest.raises(notes.NotesUnavailable, match="unreachable"):
        notes.generate("ada isi", "Kajian")


def test_model_still_loading_is_unavailable(monkeypatch):
    # 503 is recoverable — the container restarted and vLLM is warming up.
    monkeypatch.setattr(
        httpx, "post",
        lambda *a, **k: httpx.Response(
            503, json={"detail": "loading"},
            request=httpx.Request("POST", "http://notes:8080/summarize"),
        ),
    )
    with pytest.raises(notes.NotesUnavailable, match="starting up"):
        notes.generate("ada isi", "Kajian")


def test_server_error_is_a_real_failure(monkeypatch):
    # 500 means the model produced unparseable output. Retrying later
    # won't help, so this must NOT be NotesUnavailable — the session
    # should surface as an error rather than silently degrade.
    monkeypatch.setattr(
        httpx, "post",
        lambda *a, **k: httpx.Response(
            500, json={"detail": "Model did not return valid JSON"},
            request=httpx.Request("POST", "http://notes:8080/summarize"),
        ),
    )
    with pytest.raises(httpx.HTTPStatusError):
        notes.generate("ada isi", "Kajian")


def test_successful_response_passes_through(monkeypatch):
    payload = {
        "summary": "Tentang sabar.",
        "keyPoints": ["Sabar itu penting"],
        "topics": ["sabar"],
        "references": [{"type": "quran", "citation": "2:153", "note": None}],
        "actionItems": [],
    }
    monkeypatch.setattr(
        httpx, "post",
        lambda *a, **k: httpx.Response(
            200, json=payload,
            request=httpx.Request("POST", "http://notes:8080/summarize"),
        ),
    )
    assert notes.generate("ada isi", "Kajian") == payload


def test_token_is_sent_when_configured(monkeypatch):
    monkeypatch.setattr(config, "NOTES_BACKEND_TOKEN", "s3cret")
    seen = {}

    def capture(url, **kwargs):
        seen.update(kwargs.get("headers") or {})
        return httpx.Response(
            200, json={"summary": "ok"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", capture)
    notes.generate("ada isi", "Kajian")
    assert seen["Authorization"] == "Bearer s3cret"
