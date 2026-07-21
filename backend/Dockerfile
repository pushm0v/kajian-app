# GPU image for a self-hosted Qwen3-ASR-1.7B backend, served via vLLM
# (required for the live-streaming endpoint — see app/asr_model.py).
# Requires the NVIDIA Container Toolkit on the host (`docker run --gpus all
# ...` / the `deploy.resources.reservations.devices` block in
# docker-compose.yml). Confirmed host driver 595.71.05 / CUDA 13.2, which
# is backward-compatible with CUDA 12.8 userspace libs — so a too-old
# driver was ruled out as the cause of the SIGILL crash below.
#
# CUDA VERSION: pip-installed torch (pulled in by qwen-asr[vllm]==0.14.0,
# which pins torch==2.9.1) bundles its OWN CUDA 12.8 runtime libraries
# (nvidia-cuda-runtime-cu12==12.8.90, etc.) regardless of what's baked into
# this base image — the base image's system CUDA toolkit is really only
# used at `pip install` time for any packages that invoke nvcc directly.
# Was previously pinned to 12.4.1; bumped to 12.8.1 to match what
# torch/vLLM actually run with, for consistency even though the driver
# check above ruled out this being the crash's root cause. If qwen-asr's
# pinned vllm/torch versions change later, check
# https://pypi.org/pypi/torch/<version>/json for the current
# nvidia-cuda-runtime-cu12 version and match this base image to it.
#
# NOTE: uses the "devel" (not "runtime") CUDA base because vLLM's install
# can require nvcc/build tooling for some kernels.
FROM nvidia/cuda:12.8.1-devel-ubuntu22.04

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

# Verbose logging while diagnosing startup crashes: vLLM has its own
# separate logger that's quiet by default, and normal Python exceptions
# won't show anything useful if the process is dying to a hard
# segfault/abort instead of a catchable error. Drop these back down (or
# remove VLLM_LOGGING_LEVEL/CUDA_LAUNCH_BLOCKING) once the backend is
# confirmed stable — DEBUG-level vLLM logging and CUDA_LAUNCH_BLOCKING
# both add real overhead.
#
# ATEN_CPU_CAPABILITY=default forces PyTorch's CPU-side ops (which still
# run for tensor setup/preprocessing even on a GPU-focused workload) to
# use the most basic, universally-supported instruction dispatch path
# instead of auto-detecting AVX-512/AVX2. This is a well-documented
# SIGILL cause when a container/hypervisor's reported CPU features don't
# actually match what's usable at runtime — the leading hypothesis for
# this crash (exit code 132 / SIGILL right as vLLM starts loading,
# with the GPU/driver themselves already confirmed fine). Remove this if
# it doesn't fix the crash, since it disables faster CPU codepaths.
ENV VLLM_LOGGING_LEVEL=DEBUG \
    CUDA_LAUNCH_BLOCKING=1 \
    ATEN_CPU_CAPABILITY=default

CMD ["python3.11", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
