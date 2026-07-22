"""Kajian App transcription backend — Whisper large-v3 variant.

Serves the app's POST /transcribe contract (batch, post-recording) using
a self-hosted Whisper large-v3 model via faster-whisper (CTranslate2),
as an alternative to the Qwen3-ASR backend in ../backend/. Runs in its
own container so either model can be deployed independently, or both at
once on a single GPU if there's enough VRAM (faster-whisper only holds
what the model actually needs — no large upfront memory reservation like
vLLM's for the Qwen backend). See ../README.md for setup and
docs/BACKEND.md in the Flutter repo for the full /transcribe contract.

No WS /transcribe/stream endpoint here: faster-whisper has no equivalent
to Qwen3-ASR's incremental-decoding API, so live streaming during
recording isn't offered by this backend. Point the app at the Qwen
backend instead if live cloud captions are needed.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config
from .asr_model import model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kajian_whisper")

_bearer = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(_: FastAPI):
    os.makedirs(config.WORK_DIR, exist_ok=True)
    os.makedirs(config.MODEL_CACHE_DIR, exist_ok=True)
    model.load()
    yield
    shutil.rmtree(config.WORK_DIR, ignore_errors=True)


app = FastAPI(title="Kajian App Whisper Backend", lifespan=lifespan)


def _check_auth(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    if not config.API_TOKEN:
        return  # No token configured: open access (LAN-only use).
    if creds is None or creds.credentials != config.API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if model.is_loaded else "loading",
        "model": config.MODEL_SIZE,
        "device": model.device,
    }


@app.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    locale: str = Form(default="id_ID"),
    model_name: str = Form(default="", alias="model"),
    _auth: None = Depends(_check_auth),
) -> dict:
    if not model.is_loaded:
        raise HTTPException(status_code=503, detail="Model is still loading, retry shortly")

    # `model_name` (the "model" form field) is accepted for contract
    # compatibility with the app but ignored — this server only ever
    # serves config.MODEL_SIZE. Kept as a parameter so the request
    # doesn't 422.
    del model_name

    upload_id = uuid.uuid4().hex
    suffix = os.path.splitext(audio.filename or "")[1] or ".m4a"
    tmp_path = os.path.join(config.WORK_DIR, f"{upload_id}{suffix}")

    size = 0
    try:
        with open(tmp_path, "wb") as f:
            while chunk := await audio.read(1024 * 1024):
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Audio file too large")
                f.write(chunk)

        started = time.monotonic()
        segments = model.transcribe(tmp_path, locale)
        processing_ms = round((time.monotonic() - started) * 1000)
        # Duration of transcribed audio, derived from the last segment's end.
        audio_seconds = (
            max((s["endMs"] for s in segments), default=0) / 1000.0
        )
        # `processing_ms`/`audio_seconds`/`model`/`device` are additive
        # metadata for benchmarking (see benchmark/ in the Flutter repo). The
        # app ignores unknown keys and only reads `segments`.
        return {
            "segments": segments,
            "processing_ms": processing_ms,
            "audio_seconds": round(audio_seconds, 3),
            "model": config.MODEL_SIZE,
            "device": model.device,
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 - convert to the app's expected error shape
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}") from e
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
