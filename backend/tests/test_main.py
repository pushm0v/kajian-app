"""Integration tests for the FastAPI app, with the actual ASR model mocked
out (no GPU / qwen-asr install required to run these)."""

import io
import os
import struct
import wave

import pytest
from fastapi.testclient import TestClient

from app import config
from app.asr_model import model as real_model


class _FakeModel:
    """Drop-in replacement for AsrModel that returns canned text without
    touching torch/qwen_asr at all."""

    is_loaded = True
    device = "cpu"

    def normalize_language(self, locale_id):
        return (locale_id or "").split("_")[0] or None

    def transcribe_chunk(self, audio, sample_rate, language):
        return "halo dunia" if len(audio) > 0 else ""


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "WORK_DIR", str(tmp_path))
    monkeypatch.setattr(config, "API_TOKEN", "")
    monkeypatch.setattr(real_model, "_model", object())  # is_loaded truthy
    monkeypatch.setattr(real_model, "load", lambda: None)

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
    assert body["model"] == config.MODEL_ID


def test_transcribe_requires_ffmpeg_and_returns_segments(monkeypatch, client):
    # Bypass real ffmpeg/model chunking entirely and assert the endpoint
    # wires request -> transcription.transcribe_file -> response correctly.
    def fake_transcribe_file(model, audio_path, locale_id):
        assert os.path.exists(audio_path)
        assert locale_id == "id_ID"
        return [
            {"id": "0", "text": "halo dunia", "startMs": 0, "endMs": 30000, "isFinal": True},
        ]

    monkeypatch.setattr("app.main.transcribe_file", fake_transcribe_file)

    resp = client.post(
        "/transcribe",
        data={"locale": "id_ID", "model": "whisper-1"},
        files={"audio": ("kajian.wav", _make_wav_bytes(1.0), "audio/wav")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "segments": [
            {"id": "0", "text": "halo dunia", "startMs": 0, "endMs": 30000, "isFinal": True},
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
    # Will fail downstream (real transcribe_file not mocked here), but must
    # get past the 401 check, i.e. not itself return 401.
    assert resp_ok_header.status_code != 401
