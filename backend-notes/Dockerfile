# GPU image for the self-hosted notes LLM, served via vLLM in-process.
#
# Base image and CUDA reasoning are inherited from ../backend/ (the
# Qwen/vLLM ASR worker), which runs the same vllm==0.19.1 pin against this
# host's driver — that combination is already proven here, so this doesn't
# re-litigate it. In short: pip-installed torch bundles its own CUDA
# runtime regardless of the base image, so the base image's toolkit
# matters mainly at install time; NVIDIA only publishes CUDA 13.x bases on
# Ubuntu 24.04, whose `python3` is 3.12.
#
# "devel" (not "runtime"): vLLM's install can require nvcc for some
# kernels, and it JIT-compiles a CUDA utility file at engine startup.
FROM nvidia/cuda:13.2.0-devel-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# python3-dev (Python.h) + build-essential (gcc/make) are required by
# vLLM's startup JIT — without them it fails with "fatal error: Python.h:
# No such file or directory" as the engine core process starts.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-dev python3-pip build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
# --break-system-packages: Ubuntu 24.04 marks the system Python as
# externally managed (PEP 668). This is a single-purpose container, so
# installing into the system interpreter is fine and avoids a venv layer.
RUN python3 -m pip install --break-system-packages --upgrade pip \
    && python3 -m pip install --break-system-packages -r requirements.txt

COPY app ./app

EXPOSE 8080

# Weights (~5.5GB at AWQ 4-bit) download from Hugging Face on first
# startup and are cached here — mount a volume at this path (see
# docker-compose.yml) so restarts don't re-download.
ENV NOTES_MODEL_CACHE_DIR=/srv/.cache/huggingface \
    HF_HOME=/srv/.cache/huggingface

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
