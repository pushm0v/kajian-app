"""Kajian App core platform backend.

Owns everything the two ASR inference workers (../backend/, ../backend-
whisper/) deliberately don't: users (Firebase-token auth), kajian
sessions/transcripts/notes (Postgres), and audio storage (MinIO/S3 via
presigned URLs). Proxies POST /transcribe to whichever ASR worker the
caller asks for and POST /summarize to the Anthropic API — see
routers/processing.py — and WS /transcribe/stream (live captions during
recording) to the Qwen worker — see routers/streaming.py. The app never
talks to the ASR workers directly; this is the only thing that does.

Also backs the admin dashboard (../admin/, a separate Next.js app) via
routers/admin.py.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .auth import init_firebase
from .routers import admin, me, processing, sessions, streaming
from .services.storage import ensure_bucket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kajian_core")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_firebase()
    ensure_bucket()
    yield


app = FastAPI(title="Kajian App Core API", lifespan=lifespan)

# The Next.js admin app and the Flutter app (web builds, if any) both need
# CORS; native mobile requests aren't subject to it at all. Defaults to "*"
# for local development — set CORE_CORS_ORIGINS explicitly before exposing
# the API beyond your homelab network.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(me.router)
app.include_router(sessions.router)
app.include_router(processing.router)
app.include_router(admin.router)
app.include_router(streaming.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
