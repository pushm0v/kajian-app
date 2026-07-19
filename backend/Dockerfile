# GPU image for a self-hosted Qwen3-ASR-1.7B backend. Requires the NVIDIA
# Container Toolkit on the host (`docker run --gpus all ...` / the
# `deploy.resources.reservations.devices` block in docker-compose.yml).
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3-pip ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
# torch's default PyPI wheel is CPU-only; install the CUDA 12.4 build first
# so the later `pip install -r requirements.txt` sees it already satisfied.
RUN python3.11 -m pip install --upgrade pip \
    && python3.11 -m pip install torch --index-url https://download.pytorch.org/whl/cu124 \
    && python3.11 -m pip install -r requirements.txt

COPY app ./app

EXPOSE 8080

# Model weights (~4.7GB) download from Hugging Face on first startup and are
# cached in HF_HOME — mount a volume there (see docker-compose.yml) so
# restarts don't re-download.
ENV HF_HOME=/srv/.cache/huggingface

CMD ["python3.11", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
