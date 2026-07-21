"""Integration tests for the FastAPI app, with the actual Whisper model
mocked out (no GPU / faster-whisper install required to run these)."""

import io
import struct
import wave

import pytest
from fastapi.testclient import TestClient

from app import config
from app.asr_model import model as real_model


class _FakeModel:
    """Drop-in replacement for WhisperModelWrapper that returns canned
    segments without touching faster_whisper/ctranslate2 at all."""

    is_loaded = True
    device = "cpu"

    def normalize_language(self, locale_id):
        return (locale_id or "").split("_")[0] or None

    def transcribe(self, audio_path, locale_id):
        return [
            {"id": "0", "text": "halo dunia", "startMs": 0, "endMs": 1200, "isFinal": True},
        ]


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "WORK_DIR", str(tmp_path))
    monkeypatch.setattr(config, "MODEL_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "API_TOKEN", "")
    monkeypatch.setattr(real_model, "_model", object())  # is_loaded truthy
    monkeypatch.setattr(real_model, "load", lambda: None)

    fake = _FakeModel()
    monkeypatch.setattr(real_model, "transcribe", fake.transcribe)

    from app.main import app

    with TestClient(app) as c:
        yield c


def _make_wav_bytes(seconds: float, sample_rate: int = 16_000) -> bytes:
    n = int(seconds * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(struct.pack("<%dh" % n, *([0] * n)))
    return buf.getvalue()


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["model"] == config.MODEL_SIZE


def test_transcribe_returns_segments(client):
    resp = client.post(
        "/transcribe",
        data={"locale": "id_ID", "model": "whisper-1"},
        files={"audio": ("kajian.wav", _make_wav_bytes(1.0), "audio/wav")},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "segments": [
            {"id": "0", "text": "halo dunia", "startMs": 0, "endMs": 1200, "isFinal": True},
        ]
    }


def test_transcribe_rejects_oversized_upload(monkeypatch, client):
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 10)
    resp = client.post(
        "/transcribe",
        data={"locale": "id_ID"},
        files={"audio": ("kajian.wav", _make_wav_bytes(1.0), "audio/wav")},
    )
    assert resp.status_code == 413


def test_transcribe_requires_auth_when_token_configured(monkeypatch, client):
    monkeypatch.setattr(config, "API_TOKEN", "secret123")
    resp = client.post(
        "/transcribe",
        data={"locale": "id_ID"},
        files={"audio": ("kajian.wav", _make_wav_bytes(1.0), "audio/wav")},
    )
    assert resp.status_code == 401

    resp_ok_header = client.post(
        "/transcribe",
        data={"locale": "id_ID"},
        files={"audio": ("kajian.wav", _make_wav_bytes(1.0), "audio/wav")},
        headers={"Authorization": "Bearer secret123"},
    )
    assert resp_ok_header.status_code == 200


def test_transcribe_returns_503_while_model_still_loading(monkeypatch, client):
    monkeypatch.setattr(real_model, "_model", None)
    resp = client.post(
        "/transcribe",
        data={"locale": "id_ID"},
        files={"audio": ("kajian.wav", _make_wav_bytes(1.0), "audio/wav")},
    )
    assert resp.status_code == 503
