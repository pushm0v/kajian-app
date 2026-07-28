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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    return raw.lower() in ("1", "true", "yes") if raw else default


# Hugging Face model id for the ASR model.
MODEL_ID = os.environ.get("ASR_MODEL_ID", "Qwen/Qwen3-ASR-1.7B")

# Fraction of GPU memory vLLM is allowed to reserve. Both official Qwen3-ASR
# vLLM examples use 0.8; lower this on a GPU shared with other workloads.
GPU_MEMORY_UTILIZATION = _env_float("ASR_GPU_MEMORY_UTILIZATION", 0.8)

# Skip vLLM's torch.compile/CUDA-graph capture at startup. Defaults to
# True. This was briefly set to False after fixing an unrelated segfault
# (a qwen-asr/vLLM version mismatch — see asr_model.py's module docstring),
# on the theory that compilation itself was never the problem. It wasn't
# on THAT code path, but with compilation re-enabled on vLLM 0.19.1's
# native model, engine startup segfaults again — this time inside
# Inductor's compiled-graph pipeline itself (right after
# FixFunctionalizationPass), on the same RTX 3080 Ti/driver combo. Two
# separate vLLM versions and two separate model-loading paths have now
# both hit real problems in vLLM's compile pipeline on this hardware, so
# eager mode is staying on as the default rather than a one-off diagnostic.
# Set ASR_ENFORCE_EAGER=false to re-enable compilation if this is ever
# revisited (e.g. after a driver/toolkit upgrade).
ENFORCE_EAGER = _env_bool("ASR_ENFORCE_EAGER", True)

# Attention backend for the audio ENCODER specifically — a separate vLLM
# setting from the decoder LM's attention backend (there's no encoder-only
# override on our vLLM version's Python API otherwise). Defaults to
# "TORCH_SDPA" (plain torch.nn.functional.scaled_dot_product_attention,
# no custom kernel at all). History, in order of what was tried and ruled
# out on this deploy (RTX 3080 Ti / Ampere, sm_86):
#   1. vLLM's default FlashAttention-2 kernel for the encoder (a vendored
#      fork, not the PyPI flash-attn package) segfaulted during the
#      encoder's dummy/profiling forward pass, reproduced on BOTH
#      qwen-asr's old model code AND vLLM's own native Qwen3-ASR
#      implementation — ruling out an application bug. vLLM's backend
#      selection treats any GPU with compute capability >= 8.0 as
#      "supported" for that kernel with no per-architecture carve-out,
#      despite the encoder/varlen path being far less tested on Ampere
#      than on the datacenter GPUs it's mainly validated against.
#   2. Forcing TRITON_ATTN for the encoder specifically (confirmed active
#      via the "Using AttentionBackendEnum.TRITON_ATTN for
#      MMEncoderAttention" log line) still segfaulted at the identical
#      point — but with a DIFFERENT crash signature: this time inside
#      PyTorch's own C++ operator dispatcher
#      (torch::jit::invokeOperatorFromPython / c10::Dispatcher::callBoxed)
#      while looking up a registered custom op, right as Triton's JIT
#      kernels were loaded — suggesting a Triton op-registration/dispatch
#      issue on this host, not an attention-math bug.
#   3. TORCH_SDPA sidesteps both: no custom CUDA kernel, no Triton JIT,
#      no custom op dispatch — just PyTorch's built-in fused attention op.
# Set ASR_MM_ENCODER_ATTN_BACKEND= (empty) to let vLLM pick its own
# default, or back to TRITON_ATTN/FLASH_ATTN if this is ever revisited.
MM_ENCODER_ATTN_BACKEND = os.environ.get("ASR_MM_ENCODER_ATTN_BACKEND", "TORCH_SDPA")

# Caps vLLM's KV cache sizing to this many tokens instead of the model's
# full max_position_embeddings (65536). On a 12GB card there isn't enough
# free VRAM after model weights + encoder buffers to fit a 65536-token KV
# cache (vLLM computed it'd need ~7GiB against ~1.75GiB available) — engine
# startup fails outright with a clear ValueError rather than serving
# anything. First tried 16384, but the available-memory calculation is
# tight enough that vLLM's own reported ceiling (16352) sits BELOW it —
# 16384 alone still fails the same check by a hair. 8192 leaves real
# margin below that ceiling (memory available at startup can vary
# slightly run to run) while still comfortably covering a single ~30s
# audio chunk's encoder tokens plus the 4096-token generation budget (see
# SamplingParams below); nothing in this pipeline needs anywhere near the
# full 65536. Raise ASR_GPU_MEMORY_UTILIZATION instead of this if more
# headroom is ever needed and VRAM allows it.
MAX_MODEL_LEN = _env_int("ASR_MAX_MODEL_LEN", 8192)

# Chunk length used for both timestamping and to keep each inference call
# well under the model's ~20-minute limit. 30s chunks keep memory/latency
# predictable and give reasonably granular segments for the transcript view.
CHUNK_SECONDS = _env_float("ASR_CHUNK_SECONDS", 30.0)

# Overlap between consecutive chunks, to avoid cutting words at boundaries.
# Overlap audio is transcribed but trimmed from the merged text by keeping
# only each chunk's non-overlapping portion's worth of output as a whole
# segment (word-level split isn't attempted — see transcription.py).
CHUNK_OVERLAP_SECONDS = _env_float("ASR_CHUNK_OVERLAP_SECONDS", 1.0)

# How many chunks are submitted to vLLM in a single generate() call for
# batch transcription (see AsrModel.transcribe_chunks). Submitting more
# chunks per call amortizes per-call dispatch overhead better, but each
# request in a batch holds its own KV cache slot concurrently — on a GPU
# this tight on VRAM (see ASR_MAX_MODEL_LEN's comment above; this backend
# already hit a KV-cache-memory startup failure once), submitting a long
# recording's full chunk list in one call risks the same kind of OOM.
# 8 is a conservative starting point; raise it if VRAM headroom allows.
TRANSCRIBE_BATCH_SIZE = _env_int("ASR_TRANSCRIBE_BATCH_SIZE", 8)

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

# --- Live streaming (/transcribe/stream WebSocket) -------------------------
#
# These control the streaming decode loop in asr_model.py. See
# backend/README.md for what each one means; defaults here match the
# official streaming example in the Qwen3-ASR repo.
STREAM_CHUNK_SIZE_SEC = _env_float("ASR_STREAM_CHUNK_SIZE_SEC", 2.0)
STREAM_UNFIXED_CHUNK_NUM = _env_int("ASR_STREAM_UNFIXED_CHUNK_NUM", 2)
STREAM_UNFIXED_TOKEN_NUM = _env_int("ASR_STREAM_UNFIXED_TOKEN_NUM", 5)

# --- Speaker embedding (/embed-speaker) -------------------------------------
#
# Runs entirely on CPU via sherpa-onnx (Apache-2.0, no PyTorch dependency —
# a deliberate choice, since VRAM is already committed to the Qwen3-ASR
# vLLM engine above; see ASR_MAX_MODEL_LEN's comment). Baked into the image
# at build time (see Dockerfile) rather than downloaded at runtime, since
# it's a small (~27MB), static, versioned file — same treatment as model
# weights would get in a less bandwidth-constrained deploy.
#
# Model: 3D-Speaker's CAM++, bilingual (zh+en) checkpoint. No
# Indonesian-specific speaker-embedding checkpoint exists publicly; this is
# the best available proxy — it's the only option in sherpa-onnx's official
# model zoo explicitly trained across languages rather than on monolingual
# VoxCeleb-English, which matters given SVeritas benchmark data showing
# 8-23 point EER degradation on cross-language trials for English-only
# models. 192-dim output.
SPEAKER_EMBEDDING_MODEL_PATH = os.environ.get(
    "ASR_SPEAKER_EMBEDDING_MODEL_PATH",
    "/srv/models/3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx",
)
