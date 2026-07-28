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

# --- Speaker embedding (/embed-speaker) -------------------------------------
#
# Originally shipped on the Qwen worker (../backend/) as a CPU-only step,
# since that container's GPU (device 0) is already fully committed to
# vLLM's upfront memory reservation. Moved here instead: this image's
# base is already CUDA 12/cuDNN 9 (matching ctranslate2's own
# requirement), which is exactly what sherpa-onnx's GPU wheel targets —
# device 0's newer CUDA 13.2/torch 2.10 stack would risk two
# independently-bundled CUDA/cuDNN runtimes conflicting in one process.
# That reasoning holds; the *memory-headroom* assumption did not — see
# SPEAKER_EMBEDDING_PROVIDER below.
#
# Model: 3D-Speaker's CAM++, bilingual (zh+en) checkpoint, baked into the
# image at build time (see Dockerfile) — small (~27MB), static, versioned.
# No Indonesian-specific speaker-embedding checkpoint exists publicly;
# this is the best available proxy — it's the only option in sherpa-onnx's
# official model zoo explicitly trained across languages rather than on
# monolingual VoxCeleb-English, which matters given SVeritas benchmark
# data showing 8-23 point EER degradation on cross-language trials for
# English-only models. 192-dim output.
SPEAKER_EMBEDDING_MODEL_PATH = os.environ.get(
    "WHISPER_SPEAKER_EMBEDDING_MODEL_PATH",
    "/srv/models/3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx",
)

# "cpu" (default) or "cuda". Defaults to cpu: in practice, Whisper
# large-v3 at float16 was measured (nvidia-smi) using ~11.6GB of this
# card's 12GB on its own, leaving too little headroom for sherpa-onnx's
# CUDA execution provider — a small (~27MB) model still needed ~2.75GB
# for a single Conv node's workspace (ONNX Runtime's CUDA EP arena
# allocator/cuDNN algorithm search over-allocates for small models by
# default; this is a known, tunable pattern, not fixed yet here). "cuda"
# requires the sherpa-onnx GPU wheel (`sherpa-onnx==X.Y.Z+cuda12.cudnnN`),
# NOT the standard PyPI `sherpa-onnx` package — see
# Dockerfile/requirements.txt. Can also be overridden per-request (see
# main.py's /embed-speaker `provider` form field, used by the
# dev-console's CPU/GPU toggle) without restarting this container.
SPEAKER_EMBEDDING_PROVIDER = os.environ.get("WHISPER_SPEAKER_EMBEDDING_PROVIDER", "cpu")
