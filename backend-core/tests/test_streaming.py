"""Tests for WS /transcribe/stream (routers/streaming.py) — the proxy that
lets the app get live captions during recording without ever talking to
the Qwen worker directly.

Uses a real local WebSocket server as a stand-in for the Qwen worker (see
`_fake_upstream`) rather than mocking `websockets.connect`, since the bug
this most needs to catch — the relay closing the upstream connection
before its "final" reply arrives (see _relay's docstring in
routers/streaming.py) — only reproduces against a real, independent async
connection with its own timing, not an in-process mock.

Unlike test_sessions.py, these use Starlette's synchronous TestClient
(not httpx's ASGITransport) because it's the one that supports
`websocket_connect`. That in turn means these tests can't depend on
conftest.py's `_clean_db`/`_fake_storage` autouse fixtures — they're async
and require an `anyio_backend`, which a plain sync test doesn't set up,
so pytest errors before the test even runs. This module shadows both with
sync no-op fixtures of the same name (pytest resolves same-named fixtures
by nearest scope) since the streaming route never touches object storage
and only touches Postgres via `current_user_ws`'s auth check, which
doesn't commit (see routers/streaming.py) — nothing here needs cleanup.
"""

from __future__ import annotations

import asyncio
import json
import threading

import pytest
import websockets
from starlette.testclient import TestClient


async def _fake_upstream_handler(ws):
    async for message in ws:
        if message == "__end__":
            await ws.send(json.dumps({"type": "final", "text": "final transcript"}))
            break
        await ws.send(json.dumps({"type": "partial", "text": f"partial:{len(message)}"}))


class _FakeUpstreamServer:
    """Runs a real websockets server on its own thread/event loop, so the
    main pytest-anyio loop (used by the app under test) doesn't conflict
    with it."""

    def __init__(self):
        self.port: int | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def _serve():
            self._server = await websockets.serve(_fake_upstream_handler, "localhost", 0)
            self.port = self._server.sockets[0].getsockname()[1]
            self._ready.set()
            await self._server.wait_closed()

        self._loop.run_until_complete(_serve())

    def start(self) -> int:
        self._thread.start()
        self._ready.wait(timeout=5)
        return self.port

    def stop(self):
        if self._server is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self._server.close)
        self._thread.join(timeout=5)


@pytest.fixture(autouse=True)
def _clean_db():
    """Shadows conftest.py's async autouse fixture of the same name — see
    the module docstring for why these tests need a sync no-op instead.

    Still disposes app.db.engine after each test, same as the original:
    each TestClient run here spins its own independent event loop, and the
    engine's pooled asyncpg connections stay bound to whichever loop was
    active when they were first created — the next test's loop then fails
    to reuse them ("Event loop is closed"). Disposing forces a fresh pool
    lazily on next use, same fix as conftest.py's version.
    """
    import anyio

    from app.db import engine

    yield
    anyio.run(engine.dispose)


@pytest.fixture(autouse=True)
def _fake_storage():
    """Shadows conftest.py's async autouse fixture of the same name."""
    yield


@pytest.fixture
def fake_upstream(monkeypatch):
    server = _FakeUpstreamServer()
    port = server.start()
    from app import config

    monkeypatch.setattr(config, "QWEN_BACKEND_URL", f"http://localhost:{port}")
    yield
    server.stop()


def test_streaming_proxy_relays_partial_and_final(fake_upstream):
    from app.main import app

    with TestClient(app) as tc:
        with tc.websocket_connect(
            "/transcribe/stream?locale=id_ID&token=test-uid"
        ) as ws:
            ws.send_bytes(b"\x00\x01" * 50)
            first = json.loads(ws.receive_text())
            assert first == {"type": "partial", "text": "partial:100"}

            ws.send_text("__end__")
            second = json.loads(ws.receive_text())
            assert second == {"type": "final", "text": "final transcript"}


def test_streaming_proxy_rejects_missing_token(fake_upstream):
    from starlette.websockets import WebSocketDisconnect

    from app.main import app

    with TestClient(app) as tc:
        with pytest.raises(WebSocketDisconnect):
            with tc.websocket_connect("/transcribe/stream?locale=id_ID"):
                pass


def test_streaming_proxy_reports_no_backend_configured(monkeypatch):
    from app import config

    monkeypatch.setattr(config, "QWEN_BACKEND_URL", "")
    from app.main import app

    with TestClient(app) as tc:
        with tc.websocket_connect(
            "/transcribe/stream?locale=id_ID&token=test-uid"
        ) as ws:
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "error"
