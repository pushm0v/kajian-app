"""Integration tests for the FastAPI app, with the actual Whisper model
mocked out (no GPU / faster-whisper install required to run these)."""

import io
import os
import struct
import wave

import pytest
from fastapi.testclient import TestClient

from app import config
from app.asr_model import model as real_model
from app.speaker_embedding import embedder as real_embedder


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


class _FakeEmbedder:
    """Drop-in replacement for SpeakerEmbedder that returns a canned
    embedding without touching sherpa-onnx/ONNX Runtime at all."""

    is_loaded = True
    dim = 192

    def embed(self, waveform, sample_rate):
        return [0.1] * self.dim


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "WORK_DIR", str(tmp_path))
    monkeypatch.setattr(config, "MODEL_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "API_TOKEN", "")
    monkeypatch.setattr(real_model, "_model", object())  # is_loaded truthy
    monkeypatch.setattr(real_model, "load", lambda: None)

    fake = _FakeModel()
    monkeypatch.setattr(real_model, "transcribe", fake.transcribe)

    fake_embedder = _FakeEmbedder()
    monkeypatch.setattr(real_embedder, "_extractor", object())  # is_loaded truthy
    monkeypatch.setattr(real_embedder, "load", lambda: None)
    monkeypatch.setattr(real_embedder, "embed", fake_embedder.embed)

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
    body = resp.json()
    assert body["segments"] == [
        {"id": "0", "text": "halo dunia", "startMs": 0, "endMs": 1200, "isFinal": True},
    ]
    # Additive benchmarking metadata (see benchmark/ harness).
    assert isinstance(body["processing_ms"], int) and body["processing_ms"] >= 0
    assert body["audio_seconds"] == 1.2
    assert body["model"] == config.MODEL_SIZE
    assert "device" in body


def test_embed_speaker_returns_embedding(monkeypatch, client):
    # Bypass real ffmpeg decoding, same pattern as the transcribe test
    # above — only asserting the endpoint wires upload -> decode -> embed
    # -> response.
    def fake_decode_to_mono_16k(audio_path):
        assert os.path.exists(audio_path)
        import numpy as np
        return np.zeros(16_000, dtype=np.float32)

    monkeypatch.setattr("app.main.decode_to_mono_16k", fake_decode_to_mono_16k)

    resp = client.post(
        "/embed-speaker",
        files={"audio": ("kajian.wav", _make_wav_bytes(1.0), "audio/wav")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dim"] == 192
    assert len(body["embedding"]) == 192
    assert isinstance(body["processing_ms"], int) and body["processing_ms"] >= 0


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
