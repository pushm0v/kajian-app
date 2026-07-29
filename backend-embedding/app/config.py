"""Runtime configuration, read from environment variables.

All settings have sane defaults for local/homelab use; override via a `.env`
file (see `.env.example`) or real environment variables in production.
"""

from __future__ import annotations

import os


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


# --- Model selection --------------------------------------------------------
#
# Two checkpoints are baked into the image (see Dockerfile), selectable
# without a rebuild. Both come from sherpa-onnx's speaker-recognition
# model zoo and are 3D-Speaker checkpoints, so both work through the same
# SpeakerEmbeddingExtractor API — only the file differs.
#
# "campplus" (default): CAM++ bilingual zh+en, ~28MB, 192-dim. This is the
#   ONLY multilingual checkpoint in the entire sherpa-onnx zoo — every
#   ERes2Net/ERes2NetV2 variant there is zh-cn monolingual, and the
#   remaining options (WeSpeaker, NeMo TitaNet) are English/VoxCeleb-only.
#   That matters here: this app transcribes Indonesian kajian audio with
#   Arabic quotation, and SVeritas benchmark data shows 8-23 point EER
#   degradation on cross-language trials for monolingual models. Staying
#   bilingual is the conservative choice until measured otherwise.
#
# "eres2netv2": ERes2NetV2 zh-cn, ~71MB, 192-dim. A stronger architecture
#   with better benchmark scores *on Chinese*, but trained zh-cn only.
#   Provided so the two can be A/B-compared on real kajian recordings
#   rather than picking on benchmark reputation alone — on this GPU the
#   size difference is irrelevant (both are trivial against 12GB), so the
#   only real question is which generalizes better to Indonesian, and that
#   is an empirical question this codebase cannot answer a priori.
#
# Set EMBEDDING_MODEL to one of the keys below, or set
# EMBEDDING_MODEL_PATH directly to use a checkpoint outside this set.
MODEL_DIR = os.environ.get("EMBEDDING_MODEL_DIR", "/srv/models")

MODELS = {
    "campplus": "3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx",
    "eres2netv2": "3dspeaker_speech_eres2netv2_sv_zh-cn_16k-common.onnx",
}

MODEL_NAME = os.environ.get("EMBEDDING_MODEL", "campplus")


def _resolve_model_path() -> str:
    explicit = os.environ.get("EMBEDDING_MODEL_PATH", "")
    if explicit:
        return explicit
    filename = MODELS.get(MODEL_NAME)
    if filename is None:
        raise ValueError(
            f"Unknown EMBEDDING_MODEL={MODEL_NAME!r}. "
            f"Expected one of {sorted(MODELS)}, or set EMBEDDING_MODEL_PATH "
            f"to a checkpoint path directly."
        )
    return os.path.join(MODEL_DIR, filename)


MODEL_PATH = _resolve_model_path()

# --- Execution provider -----------------------------------------------------
#
# "cuda" (default) or "cpu". This service exists precisely so embedding can
# run on a GPU of its own: when this step lived in the Whisper container it
# had to default to CPU, because Whisper large-v3 at float16 was measured
# (nvidia-smi) using ~11.6GB of that card's 12GB, leaving too little for
# ONNX Runtime's CUDA execution provider — a ~27MB model still wanted
# ~2.75GB for a single Conv node's workspace (the CUDA EP's arena
# allocator and cuDNN algorithm search over-allocate for small models by
# default). With a dedicated card that pressure is gone.
#
# Still switchable per-request (see main.py's /embed-speaker `provider`
# form field) and per-deploy, so this can fall back to CPU without a
# rebuild if the GPU is unavailable or claimed by something else.
#
# "cuda" requires the sherpa-onnx GPU wheel
# (`sherpa-onnx==X.Y.Z+cuda12.cudnnN`), NOT the standard PyPI
# `sherpa-onnx` package — see Dockerfile/requirements.txt.
PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "cuda")

# CPU threads ONNX Runtime uses when provider="cpu" (ignored for "cuda").
# Defaults to all available cores: this is a single-request-at-a-time
# post-processing step (behind SpeakerEmbedder's own lock), not something
# serving concurrent traffic that needs headroom reserved. On a 4-CPU host
# this took a measured ~93s for a 44-minute recording at 1 thread.
NUM_THREADS = _env_int("EMBEDDING_NUM_THREADS", os.cpu_count() or 1)

# --- Server -----------------------------------------------------------------

# Max upload size (bytes). ~90 min of mono AAC at typical kajian recording
# bitrates comfortably fits under 300MB.
MAX_UPLOAD_BYTES = _env_int("EMBEDDING_MAX_UPLOAD_BYTES", 300 * 1024 * 1024)

# Optional bearer token required on all requests. Leave unset for local/LAN
# use only; set this before exposing the server beyond your homelab network.
API_TOKEN = os.environ.get("EMBEDDING_API_TOKEN", "")

# Directory for scratch files (uploaded audio before decoding).
WORK_DIR = os.environ.get("EMBEDDING_WORK_DIR", "/tmp/kajian-embedding")

# Sample rate ffmpeg decodes to before extraction. 16kHz is what all the
# supported checkpoints are trained at — do not change without also
# changing the model.
TARGET_SAMPLE_RATE = 16_000
