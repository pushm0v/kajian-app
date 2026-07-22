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

import anyio
import websockets
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from websockets.exceptions import ConnectionClosed

from .. import config
from ..auth import current_user_ws
from ..db import SessionLocal

logger = logging.getLogger("kajian_core")

router = APIRouter(tags=["streaming"])


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
