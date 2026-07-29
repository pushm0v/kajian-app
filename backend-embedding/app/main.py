"""Kajian App speaker embedding backend — a dedicated GPU service.

Serves POST /embed-speaker, extracting a 192-dim voice fingerprint used by
backend-core's speaker matching (see its services/speaker_matching.py) to
suggest which known speaker a session belongs to.

This ran inside ../backend-whisper/ previously. It moved out because
sharing a card with Whisper large-v3 forced the embedding step onto CPU:
Whisper's float16 weights were measured at ~11.6GB of that 12GB card,
leaving too little headroom for ONNX Runtime's CUDA execution provider
(see config.py's PROVIDER comment). On its own GPU the same model runs on
CUDA with room to spare, and the two services can be scaled, restarted,
and version-bumped independently.

The /embed-speaker request and response shapes are unchanged from the
backend-whisper implementation, so backend-core's asr_proxy.embed_speaker
needed only a URL change, not a parsing change. `model` is additive —
existing callers ignore unknown keys.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
import uuid
from contextlib import asynccontextmanager

import anyio
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config
from .audio import decode_to_mono_16k
from .speaker_embedding import embedder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kajian_embedding")

_bearer = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(_: FastAPI):
    os.makedirs(config.WORK_DIR, exist_ok=True)
    # Load eagerly at startup so the first real request doesn't pay the
    # model-load cost, and so a misconfigured model path / missing GPU
    # wheel surfaces immediately in the logs rather than on first use.
    # Deliberately not fatal: a GPU that's unavailable at boot shouldn't
    # keep the container in a crash-loop when /embed-speaker can still be
    # served by passing provider=cpu explicitly.
    try:
        embedder.load()
    except Exception:  # noqa: BLE001 - startup diagnostics, see above
        logger.exception(
            "Speaker embedding model failed to load at startup "
            "(provider=%s, model=%s); /embed-speaker will retry per-request",
            config.PROVIDER, config.MODEL_PATH,
        )
    yield
    shutil.rmtree(config.WORK_DIR, ignore_errors=True)


app = FastAPI(title="Kajian App Speaker Embedding Backend", lifespan=lifespan)


def _check_auth(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    if not config.API_TOKEN:
        return  # No token configured: open access (LAN-only use).
    if creds is None or creds.credentials != config.API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if embedder.is_loaded else "loading",
        "model": config.MODEL_NAME,
        "model_path": config.MODEL_PATH,
        "provider": embedder.provider or config.PROVIDER,
    }


@app.post("/embed-speaker")
async def embed_speaker(
    audio: UploadFile = File(...),
    provider: str = Form(default=""),
    model: str = Form(default=""),
    _auth: None = Depends(_check_auth),
) -> dict:
    """Extracts a speaker embedding from an uploaded recording.

    `provider` ("cpu"/"cuda") and `model` (a key of config.MODELS) each
    optionally override this service's configured defaults for a single
    call, reloading the extractor if they differ from what's loaded (a few
    seconds, see SpeakerEmbedder.load()). Empty means "use my default".
    Exposed so the dev-console can A/B checkpoints and fall back to CPU
    without restarting the container.
    """
    model_path = None
    if model:
        if model not in config.MODELS:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown model={model!r}. Expected one of {sorted(config.MODELS)}",
            )
        model_path = os.path.join(config.MODEL_DIR, config.MODELS[model])

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
        # decode_to_mono_16k shells out to ffmpeg and embed() runs ONNX
        # inference — both blocking, so both go off the event loop to keep
        # health checks and concurrent requests responsive.
        waveform = await anyio.to_thread.run_sync(decode_to_mono_16k, tmp_path)
        if waveform.size == 0:
            raise HTTPException(status_code=422, detail="No audio content decoded from upload")
        embedding = await anyio.to_thread.run_sync(
            embedder.embed, waveform, config.TARGET_SAMPLE_RATE, provider or None, model_path,
        )
        processing_ms = round((time.monotonic() - started) * 1000)
        logger.info(
            "Speaker embedding extracted in %dms (dim=%d, audio_samples=%d, provider=%s, model=%s)",
            processing_ms, len(embedding), waveform.size, embedder.provider, model or config.MODEL_NAME,
        )
        return {
            "embedding": embedding,
            "dim": len(embedding),
            "processing_ms": processing_ms,
            "provider": embedder.provider,
            "model": model or config.MODEL_NAME,
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 - convert to the app's expected error shape
        logger.exception("Speaker embedding extraction failed")
        raise HTTPException(status_code=500, detail=f"Speaker embedding extraction failed: {e}") from e
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
