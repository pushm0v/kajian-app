"""Kajian App transcription backend.

Serves the app's POST /transcribe contract (batch, post-recording) plus a
WS /transcribe/stream endpoint (live, during recording) using a self-hosted
Qwen/Qwen3-ASR-1.7B model via vLLM. See ../README.md for setup and
docs/BACKEND.md in the Flutter repo for the /transcribe contract (the app
also expects a /summarize endpoint, which this backend intentionally does
not implement yet — cloud note-generation stays in mock mode on the app
side until that's added separately).
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from contextlib import asynccontextmanager

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config
from .asr_model import model
from .streaming import run_streaming_session
from .transcription import transcribe_file

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kajian_asr")

_bearer = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(_: FastAPI):
    os.makedirs(config.WORK_DIR, exist_ok=True)
    model.load()
    yield
    shutil.rmtree(config.WORK_DIR, ignore_errors=True)


app = FastAPI(title="Kajian App ASR Backend", lifespan=lifespan)


def _check_auth(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    if not config.API_TOKEN:
        return  # No token configured: open access (LAN-only use).
    if creds is None or creds.credentials != config.API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if model.is_loaded else "loading",
        "model": config.MODEL_ID,
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
    # compatibility with the app but ignored — this server only ever serves
    # config.MODEL_ID. Kept as a parameter so the request doesn't 422.
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

        segments = transcribe_file(model, tmp_path, locale)
        return {"segments": segments}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 - convert to the app's expected error shape
        logger.exception("Transcription failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}") from e
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.websocket("/transcribe/stream")
async def transcribe_stream(
    websocket: WebSocket,
    locale: str = Query(default="id_ID"),
    token: str = Query(default=""),
) -> None:
    """Live incremental transcription for use *during* recording, alongside
    (not replacing) the app's existing on-device live captions. See
    streaming.py for the wire protocol.

    Bearer auth doesn't apply cleanly to a WebSocket handshake in most HTTP
    client libraries, so when ASR_API_TOKEN is set this endpoint instead
    expects `?token=...` as a query parameter.
    """
    if config.API_TOKEN and token != config.API_TOKEN:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not model.is_loaded:
        await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
        return

    await run_streaming_session(websocket, model, locale)
