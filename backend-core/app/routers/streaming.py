"""WS /transcribe/stream — relays the app's live-recording audio to the
Qwen worker (../backend/) for live captions, the same way
routers/processing.py proxies the batch POST /transcribe.

Before this existed, the app connected straight to the Qwen worker's own
WebSocket endpoint (bypassing backend-core entirely) for live streaming,
since backend-core had no equivalent — REST /transcribe and /summarize were
proxied, but the live-caption socket wasn't. This closes that gap: the app
now only ever talks to backend-core, never the ASR workers directly, and
the worker URL/token stay a server-side secret.

Only the Qwen worker supports streaming (Whisper/faster-whisper has no
incremental decoding story), so there's no `model` choice here, unlike the
batch endpoint.
"""

from __future__ import annotations

import logging
import os
import uuid

import anyio
import websockets
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from websockets.exceptions import ConnectionClosed

from .. import config, schemas
from ..auth import current_user, current_user_ws
from ..db import SessionLocal
from ..models.user import User
from ..services import asr_proxy

logger = logging.getLogger("kajian_core")

router = APIRouter(tags=["streaming"])

# A ~20s mono 16kHz PCM16 WAV is ~640KB; this leaves generous headroom for
# longer or higher-rate chunks while still rejecting anything that's
# clearly a whole recording sent to the wrong endpoint.
_MAX_CHUNK_BYTES = 25 * 1024 * 1024


@router.post("/transcribe-chunk", response_model=schemas.TranscribeChunkOut)
async def transcribe_chunk(
    audio: UploadFile = File(...),
    locale: str = Form(default="id_ID"),
    model: str = Form(default="whisper"),
    user: User = Depends(current_user),
) -> schemas.TranscribeChunkOut:
    """Transcribes one short slice of live audio and returns its text.

    Stateless by design: no session, no DB write, nothing persisted. This
    backs the app's chunked live-caption mode, where the recorder ships a
    ~20s window every few seconds purely so the user sees text appear
    while they record. The authoritative transcript still comes from the
    batch POST /sessions/{id}/transcribe pass over the whole recording
    once recording stops — that pass has full-file context, which per-chunk
    inference cannot match, so nothing here is worth persisting.

    Why this exists at all: WS /transcribe/stream (below) only works
    against the Qwen worker, since faster-whisper has no incremental
    decoding API. Chunking is how Whisper does "live" — each chunk is an
    ordinary independent transcription. The app overlaps consecutive
    chunks and stitches them client-side (see
    ChunkedTranscriptionService), because a word straddling a cut would
    otherwise be mangled in both neighbours.

    Deliberately NOT reusing the session /transcribe endpoint: that one
    reads audio from S3 and *overwrites* the session transcript, which
    would be wrong per-chunk and would round-trip through object storage
    for audio that is thrown away seconds later.
    """
    suffix = os.path.splitext(audio.filename or "")[1] or ".wav"
    tmp_path = os.path.join(config.WORK_DIR, f"chunk-{uuid.uuid4().hex}{suffix}")

    size = 0
    os.makedirs(config.WORK_DIR, exist_ok=True)
    try:
        with open(tmp_path, "wb") as f:
            while data := await audio.read(1024 * 1024):
                size += len(data)
                if size > _MAX_CHUNK_BYTES:
                    raise HTTPException(status_code=413, detail="Audio chunk too large")
                f.write(data)

        try:
            asr_model = asr_proxy.AsrModel(model)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=f"Unknown model: {model}") from e

        try:
            result = await asr_proxy.transcribe(asr_model, tmp_path, locale)
        except asr_proxy.AsrModelUnavailable as e:
            raise HTTPException(status_code=503, detail=str(e)) from e

        segments = result.get("segments", [])
        text = " ".join(
            s.get("text", "").strip() for s in segments if s.get("text", "").strip()
        )
        logger.info(
            "transcribe_chunk: user=%s bytes=%d -> %d segment(s), %d char(s)",
            user.id, size, len(segments), len(text),
        )
        return schemas.TranscribeChunkOut(text=text)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _worker_ws_url(locale: str) -> str:
    base = config.QWEN_BACKEND_URL.rstrip("/")
    ws_base = "wss://" + base.removeprefix("https://") if base.startswith("https://") else (
        "ws://" + base.removeprefix("http://")
    )
    url = f"{ws_base}/transcribe/stream?locale={locale}"
    if config.QWEN_BACKEND_TOKEN:
        url += f"&token={config.QWEN_BACKEND_TOKEN}"
    return url


@router.websocket("/transcribe/stream")
async def transcribe_stream(
    websocket: WebSocket,
    locale: str = Query(default="id_ID"),
    token: str | None = Query(default=None),
) -> None:
    # Verify the caller before accept()ing — a rejected handshake (close
    # before accept) reads as a clean 4xx-equivalent to the client rather
    # than an accepted-then-immediately-closed socket.
    async with SessionLocal() as db:
        try:
            await current_user_ws(token, db)
        except Exception:  # noqa: BLE001 - HTTPException or anything else -> reject
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    if not config.QWEN_BACKEND_URL:
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "message": "No streaming ASR backend configured (QWEN_BACKEND_URL unset)",
        })
        await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
        return

    await websocket.accept()

    try:
        async with websockets.connect(_worker_ws_url(locale), max_size=None) as upstream:
            await _relay(websocket, upstream)
    except (ConnectionClosed, OSError) as e:
        logger.warning("Upstream ASR worker connection failed: %s", e)
        try:
            await websocket.send_json({
                "type": "error",
                "message": "Streaming ASR backend unavailable",
            })
        except Exception:  # noqa: BLE001 - client socket may already be gone
            pass
    finally:
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass


async def _relay(client: WebSocket, upstream) -> None:
    """Pumps audio frames client -> upstream and JSON results upstream ->
    client concurrently until either side closes or sends `__end__`.

    After a clean "__end__", `upstream` is deliberately left open: the
    worker still owes us one final result (see backend/app/streaming.py's
    protocol), and closing it here would race that reply — instead
    `upstream_to_client` ends the task group once the worker closes its own
    end. An abrupt client disconnect (no "__end__") is different: nothing
    will make the worker ever close on its own then, so that path does
    close `upstream` itself to avoid leaking the session.
    """

    async def client_to_upstream() -> None:
        clean_end = False
        try:
            while True:
                message = await client.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                text = message.get("text")
                if text is not None:
                    await upstream.send(text)
                    if text == "__end__":
                        clean_end = True
                        break
                    continue
                data = message.get("bytes")
                if data:
                    await upstream.send(data)
        except WebSocketDisconnect:
            pass
        finally:
            if not clean_end:
                with anyio.CancelScope(shield=True):
                    try:
                        await upstream.close()
                    except Exception:  # noqa: BLE001
                        pass

    async def upstream_to_client() -> None:
        try:
            async for message in upstream:
                await client.send_text(message)
        except ConnectionClosed:
            pass

    async with anyio.create_task_group() as tg:
        tg.start_soon(client_to_upstream)
        tg.start_soon(upstream_to_client)
