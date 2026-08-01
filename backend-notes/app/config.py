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


# --- Model ------------------------------------------------------------------
#
# Qwen2.5-7B-Instruct, AWQ 4-bit (~5.5GB of weights vs ~15GB at fp16).
#
# Chosen for this specific job rather than general benchmark standing. The
# notes prompt (see notes_model.py's _SYSTEM_PROMPT, copied verbatim from
# what backend-core sent Anthropic) demands two things a small model can
# easily fail at: strict JSON-only output, and faithful handling of
# Indonesian/Malay/English/Arabic in one transcript, preserving Quran and
# Hadith citations. Qwen2.5's instruct tuning covers all four languages
# and it holds a JSON schema well under vLLM's guided decoding; the
# Llama-3.1 family at this size is weaker on Indonesian and markedly
# weaker on Arabic script.
#
# AWQ specifically (not GPTQ/GGUF): vLLM has first-class AWQ kernels, and
# 4-bit is what makes this fit alongside the speaker embedding service on
# one 12GB card. Expect a real quality gap vs Claude — see README.md's
# "Quality expectations" before trusting the citations it emits.
MODEL_ID = os.environ.get("NOTES_MODEL_ID", "Qwen/Qwen2.5-7B-Instruct-AWQ")

QUANTIZATION = os.environ.get("NOTES_QUANTIZATION", "awq")

# Fraction of the GPU vLLM may reserve. Deliberately well below the 0.8
# the ASR backend uses: this card is SHARED with ../backend-embedding/,
# whose sherpa-onnx CUDA session allocates on demand (a ~28MB model still
# wanted ~2.75GB of workspace — ONNX Runtime's CUDA EP over-allocates for
# small models). vLLM reserves its share upfront and never gives it back,
# so leaving ~45% free is what keeps embedding able to run at all.
#
# 0.55 of 12GB is ~6.6GB: enough for ~5.5GB of AWQ weights plus a modest
# KV cache at NOTES_MAX_MODEL_LEN. Raise only if embedding is moved off
# this card.
GPU_MEMORY_UTILIZATION = _env_float("NOTES_GPU_MEMORY_UTILIZATION", 0.55)

# Context window. A 45-minute kajian transcript runs roughly 8-12k tokens,
# so 16k covers the realistic worst case with room for the prompt and the
# generated notes. Larger windows cost KV cache memory this card can't
# spare — transcripts longer than this are truncated (see notes_model.py).
MAX_MODEL_LEN = _env_int("NOTES_MAX_MODEL_LEN", 16384)

# Cap on generated notes length. The response is a single JSON object with
# a short summary, a handful of key points, topics, references, and action
# items — 1500 was the Anthropic-side budget and is generous for that.
MAX_TOKENS = _env_int("NOTES_MAX_TOKENS", 1500)

# Near-greedy. Notes should be faithful to the transcript, not creative,
# and low temperature also makes the model far more reliable at emitting
# well-formed JSON.
TEMPERATURE = _env_float("NOTES_TEMPERATURE", 0.2)

# Skip vLLM's torch.compile/CUDA-graph capture at startup. The ASR backend
# hit repeated startup segfaults with compilation enabled on this exact
# GPU/driver combination (see ../backend/app/config.py's history) — this
# defaults to eager for the same reason, trading some throughput for a
# startup that reliably completes. This is a once-per-session workload,
# not a latency-critical one.
ENFORCE_EAGER = os.environ.get("NOTES_ENFORCE_EAGER", "true").lower() != "false"

# --- Server -----------------------------------------------------------------

# Optional bearer token required on all requests. Leave unset for local/LAN
# use only; set this before exposing the server beyond your homelab network.
# Must match backend-core's NOTES_BACKEND_TOKEN.
API_TOKEN = os.environ.get("NOTES_API_TOKEN", "")

# Where model weights are cached. Mount a volume here (see
# docker-compose.yml) so restarts don't re-download ~5.5GB.
MODEL_CACHE_DIR = os.environ.get("NOTES_MODEL_CACHE_DIR", "/srv/.cache/huggingface")
