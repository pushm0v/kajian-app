# GPU image for the dedicated speaker embedding service.
#
# CUDA/cuDNN version: sherpa-onnx's GPU wheel (see requirements.txt) is
# built against CUDA 12 + cuDNN 9, so this base matches that exactly. This
# is the same base as ../backend-whisper/ and deliberately NOT the Qwen
# worker's newer CUDA 13.2/torch 2.10 stack — bundling two independent
# CUDA runtimes in one process is a real conflict risk, which is why this
# service is its own container rather than an addition to ../backend/.
#
# "runtime" (not "devel"): ONNX Runtime ships prebuilt kernels and
# JIT-compiles nothing at startup, so no nvcc/build tooling is needed.
FROM nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg decodes uploads to the raw waveform sherpa-onnx needs (app/audio.py).
# curl fetches the model checkpoints below, at build time only.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3-pip ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN python3.11 -m pip install --upgrade pip \
    && python3.11 -m pip install -r requirements.txt

# Both selectable checkpoints (see app/config.py's MODELS) are baked in
# rather than downloaded at runtime — small, static, versioned, and it
# keeps startup offline. Checksums are verified at build time: these URLs
# point at a mutable GitHub release tag, so pinning the bytes is what
# actually guarantees a reproducible image.
#
# campplus   (~28MB) — CAM++ bilingual zh+en, the default. The only
#                      multilingual checkpoint in the sherpa-onnx zoo.
# eres2netv2 (~71MB) — ERes2NetV2 zh-cn, stronger but Chinese-only.
#                      Baked in so the two can be A/B-compared on real
#                      audio without a rebuild.
ARG MODEL_BASE_URL=https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models
RUN mkdir -p /srv/models && cd /srv/models && \
    curl -fL -O "${MODEL_BASE_URL}/3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx" && \
    curl -fL -O "${MODEL_BASE_URL}/3dspeaker_speech_eres2netv2_sv_zh-cn_16k-common.onnx" && \
    echo "aa3cfc16963a10586a9393f5035d6d6b57e98d358b347f80c2a30bf4f00ceba2  3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx" > checksums.txt && \
    echo "bf1a75b9930474cf3389ef415e6e5d38ca96fea4a3a00f7e301d080a58ee2239  3dspeaker_speech_eres2netv2_sv_zh-cn_16k-common.onnx" >> checksums.txt && \
    sha256sum -c checksums.txt

COPY app ./app

EXPOSE 8080

CMD ["python3.11", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
