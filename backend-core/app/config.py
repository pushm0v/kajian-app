"""Runtime configuration, read from environment variables.

All settings have sane defaults for local/homelab use; override via a `.env`
file (see `.env.example`) or real environment variables in production.
"""

from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# --- Database ---------------------------------------------------------------
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://kajian:kajian@localhost:5432/kajian",
)

# --- Firebase Auth (token verification) -------------------------------------
# Path to a Firebase service account JSON key (Project Settings > Service
# Accounts > Generate new private key in the Firebase console). Required in
# production; see README.md for how to obtain and mount this file.
FIREBASE_SERVICE_ACCOUNT_PATH = os.environ.get(
    "FIREBASE_SERVICE_ACCOUNT_PATH", "/run/secrets/firebase-service-account.json"
)

# DEV ONLY: when true, skips real Firebase token verification and instead
# trusts an `X-Dev-User-Id` header as the Firebase UID directly. Never enable
# this outside local development — see app/auth.py.
DEV_AUTH_BYPASS = _env_bool("CORE_DEV_AUTH_BYPASS", False)

# --- Object storage (MinIO / S3-compatible) ---------------------------------
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL", "http://localhost:9000")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
S3_BUCKET = os.environ.get("S3_BUCKET", "kajian-audio")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")
# Whether S3_ENDPOINT_URL uses a self-signed/internal cert (MinIO defaults to
# plain HTTP on a LAN, so this defaults false).
S3_USE_SSL = _env_bool("S3_USE_SSL", False)

# How long a presigned upload/download URL stays valid.
PRESIGNED_URL_TTL_SECONDS = _env_int("PRESIGNED_URL_TTL_SECONDS", 3600)

# --- ASR worker proxy --------------------------------------------------------
# Base URLs of the two inference workers this service proxies /transcribe
# to (see ../backend/ and ../backend-whisper/). Empty means that model
# isn't available — requests naming it get a 503, not silently routed
# elsewhere.
QWEN_BACKEND_URL = os.environ.get("QWEN_BACKEND_URL", "")
WHISPER_BACKEND_URL = os.environ.get("WHISPER_BACKEND_URL", "")

# Bearer tokens sent to the ASR workers above, if they enforce one
# (ASR_API_TOKEN / WHISPER_API_TOKEN in their own .env files).
QWEN_BACKEND_TOKEN = os.environ.get("QWEN_BACKEND_TOKEN", "")
WHISPER_BACKEND_TOKEN = os.environ.get("WHISPER_BACKEND_TOKEN", "")

# --- AI notes (Anthropic) ----------------------------------------------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DEFAULT_NOTES_MODEL = os.environ.get("DEFAULT_NOTES_MODEL", "claude-sonnet-5")

# --- Misc --------------------------------------------------------------------
MAX_UPLOAD_BYTES = _env_int("CORE_MAX_UPLOAD_BYTES", 300 * 1024 * 1024)
WORK_DIR = os.environ.get("CORE_WORK_DIR", "/tmp/kajian-core")

# Comma-separated list of allowed CORS origins (e.g. the admin app's URL).
# "*" (the default) is fine for local development; set this explicitly
# before exposing the API beyond your homelab network.
CORS_ORIGINS = [
    o.strip() for o in os.environ.get("CORE_CORS_ORIGINS", "*").split(",") if o.strip()
]
