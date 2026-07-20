"""WebSocket live-streaming transcription session.

Protocol (see backend/README.md for the full spec and rationale):

  Client -> Server: binary WebSocket frames of raw PCM16LE mono audio at
    config.TARGET_SAMPLE_RATE (16kHz) — i.e. exactly what the app's
    `record` package's startStream() produces when configured for
    AudioEncoder.pcm16bits at 16000Hz/1 channel. Any frame size is fine;
    audio is buffered and only decoded once enough has accumulated for
    the model's chunk_size_sec.

    A text frame containing exactly "__end__" tells the server the client
    is done sending audio; the server flushes, sends one final result, and
    closes the connection.

  Server -> Client: JSON text frames, either
    {"type": "partial", "text": "..."}   -- cumulative transcript so far
    {"type": "final",   "text": "..."}   -- last message before closing
    {"type": "error",   "message": "..."}

This is intentionally a much simpler contract than the batch /transcribe
endpoint's segment list — there's no chunk-boundary timestamping here, just
a running cumulative transcript, since that's what Qwen3-ASR's streaming
API itself produces (see asr_model.py's module docstring). The app is
expected to treat this the same way it already treats on-device live
captions: as best-effort interim text, replaced/finalized once the
post-recording accurate pass (POST /transcribe) completes.
"""

from __future__ import annotations

import json
import logging

import numpy as np
from fastapi import WebSocket, WebSocketDisconnect

from .asr_model import AsrModel

logger = logging.getLogger("kajian_asr")

_END_SENTINEL = "__end__"


async def run_streaming_session(websocket: WebSocket, model: AsrModel, locale: str | None) -> None:
    await websocket.accept()

    language = model.normalize_language(locale)
    state = model.new_streaming_state()
    logger.info("Streaming session started, language=%s", language or "auto")

    try:
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            text = message.get("text")
            if text == _END_SENTINEL:
                break
            if text is not None:
                # Ignore any other unexpected text frames rather than erroring
                # the whole session over a stray message.
                continue

            data = message.get("bytes")
            if not data:
                continue

            pcm = np.frombuffer(data, dtype="<i2")  # PCM16LE -> int16
            cumulative_text = model.streaming_transcribe(pcm, state)
            await websocket.send_text(json.dumps({
                "type": "partial",
                "text": cumulative_text,
            }))

        final_text = model.finish_streaming(state)
        await websocket.send_text(json.dumps({
            "type": "final",
            "text": final_text,
        }))

    except WebSocketDisconnect:
        logger.info("Streaming session disconnected by client")
    except Exception as e:  # noqa: BLE001
        logger.exception("Streaming session failed")
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e),
            }))
        except Exception:  # noqa: BLE001 - best effort, socket may already be closed
            pass
    finally:
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass
