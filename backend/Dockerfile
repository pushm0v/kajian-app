# GPU image for a self-hosted Qwen3-ASR-1.7B backend, served via vLLM
# (required for the live-streaming endpoint — see app/asr_model.py).
# Requires the NVIDIA Container Toolkit on the host (`docker run --gpus all
# ...` / the `deploy.resources.reservations.devices` block in
# docker-compose.yml). Host driver 595.71.05 / CUDA 13.2.
#
# Matches the host's CUDA 13.2 driver directly (was 12.8.1, bumped while
# investigating a persistent encoder-profiling segfault on this GPU — see
# ASR_MM_ENCODER_ATTN_BACKEND's comment in config.py for that
# investigation's full history; whether the CUDA version itself was ever
# a factor is unconfirmed, this was one of the remaining variables to
# rule out). NVIDIA only publishes CUDA 13.x base images on Ubuntu 24.04
# (no -ubuntu22.04 variant exists for this CUDA series), which is why
# this now installs Python 3.12 (24.04's default `python3`/`python3-dev`)
# instead of the previous 3.11 — confirmed the full pinned dependency
# stack (vllm==0.19.1, torch==2.10.0, numba==0.61.2, numpy<2.3,
# transformers) all publish proper cp312 wheels, no source builds needed.
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
FROM nvidia/cuda:13.2.0-devel-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# python3-dev (Python.h) + build-essential (gcc/make) are required by
# vLLM, which JIT-compiles a CUDA utility file at engine startup — without
# them it fails with "fatal error: Python.h: No such file or directory"
# right as the vLLM engine core process starts. Ubuntu 24.04's `python3`
# is 3.12 (no separate `python3.12` package/venv/dev split needed the way
# 22.04 required explicitly naming `python3.11` — 24.04's `python3` IS
# 3.12).
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-dev python3-pip ffmpeg build-essential curl \
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
# Ubuntu 24.04's system Python is PEP 668 "externally managed"
# (apt-installed pip refuses a bare `pip install` outside a venv) —
# --break-system-packages is safe here since this image exists solely to
# run this one app; there's no other system Python consumer to protect.
#
# Deliberately NOT running `pip install --upgrade pip` first: apt's pip
# package (24.0) is installed without the RECORD metadata file pip's own
# in-place-upgrade path expects, so pip trying to uninstall itself to
# upgrade fails ("Cannot uninstall pip 24.0, RECORD file not found").
# 24.0 is new enough to install everything in requirements.txt correctly.
RUN python3 -m pip install --break-system-packages -r requirements.txt

# Speaker embedding model (sherpa-onnx's CAM++ bilingual checkpoint, see
# app/config.py's SPEAKER_EMBEDDING_MODEL_PATH comment for why this one).
# Baked into the image rather than downloaded at runtime — small (~27MB),
# static, versioned, and this avoids a GitHub-releases dependency at
# container startup (unlike the ASR model, which is large enough and
# updated often enough to justify HF_HOME's runtime-download+cache-volume
# approach below).
RUN mkdir -p /srv/models && \
    curl -fL -o /srv/models/3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx \
        https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx

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
# enforce_eager (config.py's ASR_ENFORCE_EAGER, default true) and a forced
# attention backend (previously VLLM_ATTENTION_BACKEND=TRITON_ATTN, since
# removed) were first tried to fix a segfault whose real cause turned out
# to be app/asr_model.py going through the `qwen-asr` package's own
# out-of-tree vLLM model registration, written against vllm==0.14.0's
# internals and never updated for vLLM's later native Qwen3-ASR support.
# Calling vllm.LLM(...) directly (see asr_model.py) removes that
# version-skewed code path entirely — but with compilation re-enabled on
# vLLM's own native model, engine startup segfaults again, this time
# inside Inductor's compiled-graph pipeline itself, on the same GPU/driver
# combo (RTX 3080 Ti). enforce_eager is staying on as the default for that
# reason; see config.py's ASR_ENFORCE_EAGER comment for the full history.
ENV VLLM_LOGGING_LEVEL=DEBUG \
    CUDA_LAUNCH_BLOCKING=1 \
    ATEN_CPU_CAPABILITY=default

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "debug"]
