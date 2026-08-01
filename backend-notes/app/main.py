"""Kajian App notes backend — self-hosted LLM summarization.

Serves POST /summarize, turning a transcript into the structured study
notes backend-core persists as a KajianNote. This replaces the Anthropic
API call that used to live in backend-core/app/services/notes.py, so no
external API key is needed and transcripts never leave the host.

Runs on GPU device 0, SHARED with ../backend-embedding/. That sharing is
why NOTES_GPU_MEMORY_UTILIZATION defaults to 0.55 rather than the 0.8 the
ASR backend uses — vLLM reserves its share upfront and never releases it,
and the embedding service's ONNX Runtime CUDA session needs to be able to
allocate on demand alongside it. See config.py for the numbers.

Device 1 stays dedicated to ../backend-whisper/, whose large-v3 weights
already occupy ~11.6GB of that card.
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

import anyio
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import config
from .notes_model import model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kajian_notes")

_bearer = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Loaded eagerly so the first real request doesn't pay a multi-minute
    # model load, and so a bad model id / insufficient VRAM surfaces in the
    # logs at startup rather than mid-job. Not fatal: /summarize returns
    # 503 until it succeeds, which backend-core treats as "notes
    # unavailable" and degrades on, rather than failing the session.
    try:
        await anyio.to_thread.run_sync(model.load)
    except Exception:  # noqa: BLE001 - startup diagnostics, see above
        logger.exception(
            "Notes model failed to load at startup (model=%s); /summarize "
            "will return 503 until this is resolved", config.MODEL_ID,
        )
    yield


app = FastAPI(title="Kajian App Notes Backend", lifespan=lifespan)


def _check_auth(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> None:
    if not config.API_TOKEN:
        return  # No token configured: open access (LAN-only use).
    if creds is None or creds.credentials != config.API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


class SummarizeIn(BaseModel):
    transcript: str
    title: str | None = None


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if model.is_loaded else "loading",
        "model": config.MODEL_ID,
        "quantization": config.QUANTIZATION,
    }


@app.post("/summarize")
async def summarize(body: SummarizeIn, _auth: None = Depends(_check_auth)) -> dict:
    """Generates structured notes from a transcript.

    Returns backend-core's exact KajianNote shape (summary, keyPoints,
    topics, references, actionItems) — see notes_model.py's module
    docstring on why that schema is copied verbatim rather than redefined.

    503 while the model is still loading: backend-core maps that to
    "notes unavailable" and leaves the session at `transcribed` rather
    than failing it, so a restart mid-session degrades gracefully.
    """
    if not model.is_loaded:
        raise HTTPException(
            status_code=503, detail="Notes model is still loading, retry shortly",
        )

    started = time.monotonic()
    try:
        # Blocking GPU inference — off the event loop so health checks and
        # concurrent requests aren't stalled for the whole generation.
        result = await anyio.to_thread.run_sync(
            model.generate, body.transcript, body.title,
        )
    except ValueError as e:
        # Model produced unparseable output. A real failure, not an
        # outage — retrying later won't help.
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001 - convert to the app's error shape
        logger.exception("Notes generation failed")
        raise HTTPException(status_code=500, detail=f"Notes generation failed: {e}") from e

    logger.info(
        "Notes generated in %.1fs (transcript_chars=%d, key_points=%d, refs=%d)",
        time.monotonic() - started, len(body.transcript),
        len(result["keyPoints"]), len(result["references"]),
    )
    return result
