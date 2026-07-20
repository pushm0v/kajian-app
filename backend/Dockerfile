# GPU image for a self-hosted Qwen3-ASR-1.7B backend, served via vLLM
# (required for the live-streaming endpoint — see app/asr_model.py).
# Requires the NVIDIA Container Toolkit on the host (`docker run --gpus all
# ...` / the `deploy.resources.reservations.devices` block in
# docker-compose.yml).
#
# NOTE: uses the "devel" (not "runtime") CUDA base because vLLM's install
# can require nvcc/build tooling for some kernels. If you hit a build error
# during `pip install qwen-asr[vllm]`, check vLLM's current install docs
# (https://docs.vllm.ai/en/latest/getting_started/installation/gpu.html)
# for whether a plain "runtime" base is sufficient for your vLLM version —
# this wasn't pinned down precisely at the time this Dockerfile was written.
FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3-pip ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
# qwen-asr[vllm] pulls vLLM 0.14.0 (pinned by qwen-asr itself) plus a
# compatible torch build automatically.
RUN python3.11 -m pip install --upgrade pip \
    && python3.11 -m pip install -r requirements.txt

COPY app ./app

EXPOSE 8080

# Model weights (~4.7GB) download from Hugging Face on first startup and are
# cached in HF_HOME — mount a volume there (see docker-compose.yml) so
# restarts don't re-download.
ENV HF_HOME=/srv/.cache/huggingface

CMD ["python3.11", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
