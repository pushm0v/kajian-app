# GPU image for a self-hosted Whisper large-v3 backend via faster-whisper
# (CTranslate2). A sibling to ../backend/ (Qwen3-ASR/vLLM) — runs in its
# own container so either model can be deployed independently, or both at
# once on a single GPU (faster-whisper only holds what the model actually
# needs in VRAM, unlike vLLM's large upfront reservation for the Qwen
# backend).
#
# Uses a "runtime" (not "devel") CUDA base — unlike the Qwen/vLLM backend,
# faster-whisper doesn't JIT-compile anything at startup, so no nvcc/build
# tooling is needed here.
#
# CUDA/cuDNN version: ctranslate2>=4.0,<5 (pinned transitively by
# faster-whisper's own requirements.txt) targets CUDA 12 + cuDNN 9 — this
# base image matches that. If you bump faster-whisper to a version that
# pulls a different ctranslate2 range, check
# https://github.com/SYSTRAN/faster-whisper#gpu for the currently
# compatible CUDA/cuDNN combination before changing this image.
FROM nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Note: faster-whisper itself decodes audio via PyAV (bundles its own
# FFmpeg libraries, no system ffmpeg needed for /transcribe). ffmpeg IS
# needed here for /embed-speaker's decode step (see app/audio.py) — that
# path was ported as-is from ../backend/, which does shell out to it.
# curl is needed once, below, to fetch the speaker embedding model file.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3-pip ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN python3.11 -m pip install --upgrade pip \
    && python3.11 -m pip install -r requirements.txt

# Speaker embedding model (sherpa-onnx's CAM++ bilingual checkpoint, see
# app/config.py's SPEAKER_EMBEDDING_MODEL_PATH comment for why this one
# lives here rather than on the Qwen worker). Baked into the image rather
# than downloaded at runtime — small (~27MB), static, versioned.
RUN mkdir -p /srv/models && \
    curl -fL -o /srv/models/3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx \
        https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx

COPY app ./app

EXPOSE 8080

# Model weights download from Hugging Face on first startup (~3GB at
# int8_float16, ~6GB at float16) and are cached here — mount a volume at
# this path (see docker-compose.yml) so restarts don't re-download.
ENV WHISPER_MODEL_CACHE_DIR=/srv/.cache/whisper

CMD ["python3.11", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
