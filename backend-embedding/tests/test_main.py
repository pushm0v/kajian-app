"""Integration tests for the FastAPI app, with the actual sherpa-onnx
extractor mocked out (no GPU / sherpa-onnx install required to run these).
"""

import io
import os
import struct
import wave

import pytest
from fastapi.testclient import TestClient

from app import config
from app.speaker_embedding import embedder as real_embedder


class _FakeEmbedder:
    """Drop-in replacement for SpeakerEmbedder that returns a canned
    embedding without touching sherpa-onnx/ONNX Runtime at all. Records
    the provider/model it was called with so the override plumbing can be
    asserted."""

    dim = 192

    def __init__(self):
        self.calls = []

    def embed(self, waveform, sample_rate, provider=None, model_path=None):
        self.calls.append({"provider": provider, "model_path": model_path})
        return [0.1] * self.dim


@pytest.fixture()
def fake_embedder(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "WORK_DIR", str(tmp_path))
    monkeypatch.setattr(config, "API_TOKEN", "")
    fake = _FakeEmbedder()
    monkeypatch.setattr(real_embedder, "_extractor", object())  # is_loaded truthy
    monkeypatch.setattr(real_embedder, "_provider", "cuda")
    monkeypatch.setattr(real_embedder, "load", lambda *a, **k: None)
    monkeypatch.setattr(real_embedder, "embed", fake.embed)
    return fake


@pytest.fixture()
def client(monkeypatch, fake_embedder):
    # Bypass real ffmpeg decoding — these tests assert the endpoint wires
    # upload -> decode -> embed -> response, not ffmpeg itself.
    def fake_decode_to_mono_16k(audio_path):
        assert os.path.exists(audio_path)
        import numpy as np
        return np.zeros(16_000, dtype=np.float32)

    monkeypatch.setattr("app.main.decode_to_mono_16k", fake_decode_to_mono_16k)

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
    assert body["model"] == config.MODEL_NAME


def test_embed_speaker_returns_embedding(client):
    resp = client.post(
        "/embed-speaker",
        files={"audio": ("kajian.wav", _make_wav_bytes(1.0), "audio/wav")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dim"] == 192
    assert len(body["embedding"]) == 192
    assert isinstance(body["processing_ms"], int) and body["processing_ms"] >= 0
    # Response shape must stay compatible with backend-core's
    # asr_proxy.embed_speaker, which reads result["embedding"].
    assert body["model"] == config.MODEL_NAME


def test_embed_speaker_forwards_provider_override(client, fake_embedder):
    resp = client.post(
        "/embed-speaker",
        data={"provider": "cpu"},
        files={"audio": ("kajian.wav", _make_wav_bytes(1.0), "audio/wav")},
    )
    assert resp.status_code == 200
    assert fake_embedder.calls[-1]["provider"] == "cpu"


def test_embed_speaker_forwards_model_override(client, fake_embedder):
    resp = client.post(
        "/embed-speaker",
        data={"model": "eres2netv2"},
        files={"audio": ("kajian.wav", _make_wav_bytes(1.0), "audio/wav")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "eres2netv2"
    assert fake_embedder.calls[-1]["model_path"].endswith(
        config.MODELS["eres2netv2"]
    )


def test_embed_speaker_rejects_unknown_model(client):
    resp = client.post(
        "/embed-speaker",
        data={"model": "not-a-real-model"},
        files={"audio": ("kajian.wav", _make_wav_bytes(1.0), "audio/wav")},
    )
    assert resp.status_code == 422


def test_embed_speaker_rejects_oversized_upload(monkeypatch, client):
    monkeypatch.setattr(config, "MAX_UPLOAD_BYTES", 10)
    resp = client.post(
        "/embed-speaker",
        files={"audio": ("kajian.wav", _make_wav_bytes(1.0), "audio/wav")},
    )
    assert resp.status_code == 413


def test_embed_speaker_requires_token_when_configured(monkeypatch, client):
    monkeypatch.setattr(config, "API_TOKEN", "secret")
    resp = client.post(
        "/embed-speaker",
        files={"audio": ("kajian.wav", _make_wav_bytes(1.0), "audio/wav")},
    )
    assert resp.status_code == 401
