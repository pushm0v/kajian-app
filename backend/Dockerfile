# GPU image for a self-hosted Qwen3-ASR-1.7B backend, served via vLLM
# (required for the live-streaming endpoint — see app/asr_model.py).
# Requires the NVIDIA Container Toolkit on the host (`docker run --gpus all
# ...` / the `deploy.resources.reservations.devices` block in
# docker-compose.yml). Confirmed host driver 595.71.05 / CUDA 13.2, which
# is backward-compatible with CUDA 12.8 userspace libs — so a too-old
# driver was ruled out as the cause of the SIGILL crash below.
#
# CUDA VERSION: pip-installed torch (pulled in transitively by
# vllm==0.19.1, pinned in requirements.txt) bundles its OWN CUDA runtime
# libraries regardless of what's baked into this base image — the base
# image's system CUDA toolkit is really only used at `pip install` time for
# any packages that invoke nvcc directly. If the pinned vllm version
# changes later, check https://pypi.org/pypi/torch/<version>/json for the
# current nvidia-cuda-runtime-cu12 version and match this base image to it.
#
# NOTE: uses the "devel" (not "runtime") CUDA base because vLLM's install
# can require nvcc/build tooling for some kernels.
FROM nvidia/cuda:12.8.1-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# python3.11-dev (Python.h) + build-essential (gcc/make) are required by
# vLLM, which JIT-compiles a CUDA utility file at engine startup — without
# them it fails with "fatal error: Python.h: No such file or directory"
# right as the vLLM engine core process starts.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3.11-dev python3-pip ffmpeg build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

# Historical note: this image used to install a stub `nagisa` package here
# to work around a SIGILL crash caused by the `qwen-asr` package's forced
# aligner pulling in a prebuilt dyNET binary compiled with `-march=native`.
# That whole code path is gone now that app/asr_model.py calls vllm.LLM(...)
# directly instead of going through qwen-asr's wrapper — nagisa/dynet are
# never imported. See git history (stubs/nagisa_stub/, removed) if this
# ever needs revisiting.

COPY requirements.txt .
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
# ATEN_CPU_CAPABILITY=default forces PyTorch's CPU-side ops onto the
# safest, universally-supported instruction dispatch path. This was an
# earlier attempt at fixing a since-resolved SIGILL crash, before `dmesg`
# on the deploy host pinpointed the actual cause as qwen-asr's nagisa/dynet
# dependency (see the Dockerfile's history/git log — that whole code path
# is gone now, see WORKDIR /srv above). Left in place as a harmless extra
# safety margin — remove if it's ever confirmed unnecessary, since it
# disables some faster CPU codepaths.
#
# enforce_eager and a forced attention backend (previously
# VLLM_ATTENTION_BACKEND=TRITON_ATTN) were tried and did NOT fix a
# different, later segfault — that crash's real cause turned out to be
# app/asr_model.py going through the `qwen-asr` package's own out-of-tree
# vLLM model registration, written against vllm==0.14.0's internals and
# never updated for vLLM's later native Qwen3-ASR support. Calling
# vllm.LLM(...) directly (see asr_model.py) removes that version-skewed
# code path entirely, so neither workaround is needed anymore.
ENV VLLM_LOGGING_LEVEL=DEBUG \
    CUDA_LAUNCH_BLOCKING=1 \
    ATEN_CPU_CAPABILITY=default

CMD ["python3.11", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
