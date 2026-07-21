"""Runtime configuration, read from environment variables.

All settings have sane defaults for local/homelab use; override via a `.env`
file (see `.env.example`) or real environment variables in production.
"""

from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


# Faster-whisper model size or a Hugging Face/CTranslate2 model id/path.
# "large-v3" downloads ~3GB (int8) to ~6GB (float16) of weights on first use.
MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "large-v3")

# "cuda" or "cpu". Unlike the Qwen/vLLM backend, faster-whisper doesn't
# reserve a large upfront memory pool — it only holds what the model
# actually needs, so this can comfortably share a GPU with the Qwen
# backend's container as long as both models' weights fit in VRAM at once.
DEVICE = os.environ.get("WHISPER_DEVICE", "cuda")

# CTranslate2 compute type. "float16" needs ~6GB VRAM for large-v3 and is
# the highest-accuracy option; "int8_float16" roughly halves that (~3GB)
# with a small accuracy tradeoff — a good choice if running alongside
# another GPU workload (e.g. the Qwen backend) on a single card.
COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "float16")

# Directory faster-whisper caches downloaded model weights in. Mount a
# volume here (see docker-compose.yml) so restarts don't re-download.
MODEL_CACHE_DIR = os.environ.get("WHISPER_MODEL_CACHE_DIR", "/srv/.cache/whisper")

# Max upload size for the /transcribe endpoint (bytes). ~90 min of mono AAC
# at typical kajian recording bitrates comfortably fits under 300MB.
MAX_UPLOAD_BYTES = _env_int("WHISPER_MAX_UPLOAD_BYTES", 300 * 1024 * 1024)

# Optional bearer token required on all requests. Leave unset for local/LAN
# use only; set this before exposing the server beyond your homelab network.
API_TOKEN = os.environ.get("WHISPER_API_TOKEN", "")

# Directory for scratch files (uploaded audio before transcription).
WORK_DIR = os.environ.get("WHISPER_WORK_DIR", "/tmp/kajian-whisper")

# Sample rate faster-whisper/ffmpeg decode to.
TARGET_SAMPLE_RATE = 16_000
