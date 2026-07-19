"""Runtime configuration, read from environment variables.

All settings have sane defaults for local/homelab use; override via a `.env`
file (see `.env.example`) or real environment variables in production.
"""

from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


# Hugging Face model id for the ASR model.
MODEL_ID = os.environ.get("ASR_MODEL_ID", "Qwen/Qwen3-ASR-1.7B")

# "cuda", "cpu", or "auto" (auto-detect at startup).
DEVICE = os.environ.get("ASR_DEVICE", "auto")

# Torch dtype for model weights: "bfloat16", "float16", or "float32".
TORCH_DTYPE = os.environ.get("ASR_TORCH_DTYPE", "bfloat16")

# Chunk length used for both timestamping and to keep each inference call
# well under the model's ~20-minute limit. 30s chunks keep memory/latency
# predictable and give reasonably granular segments for the transcript view.
CHUNK_SECONDS = _env_float("ASR_CHUNK_SECONDS", 30.0)

# Overlap between consecutive chunks, to avoid cutting words at boundaries.
# Overlap audio is transcribed but trimmed from the merged text by keeping
# only each chunk's non-overlapping portion's worth of output as a whole
# segment (word-level split isn't attempted — see transcription.py).
CHUNK_OVERLAP_SECONDS = _env_float("ASR_CHUNK_OVERLAP_SECONDS", 1.0)

# Sample rate the model expects.
TARGET_SAMPLE_RATE = 16_000

# Max upload size for the /transcribe endpoint (bytes). ~90 min of mono AAC
# at typical kajian recording bitrates comfortably fits under 300MB.
MAX_UPLOAD_BYTES = _env_int("ASR_MAX_UPLOAD_BYTES", 300 * 1024 * 1024)

# Optional bearer token required on all requests. Leave unset for local/LAN
# use only; set this before exposing the server beyond your homelab network.
API_TOKEN = os.environ.get("ASR_API_TOKEN", "")

# Directory for scratch files (uploaded audio, converted wav chunks).
WORK_DIR = os.environ.get("ASR_WORK_DIR", "/tmp/kajian-asr")
