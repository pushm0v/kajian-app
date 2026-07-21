# Kajian App Whisper backend

A self-hosted transcription backend for the Kajian App, running **Whisper
large-v3** via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
(CTranslate2) on your own GPU — a sibling to `../backend/` (Qwen3-ASR via
vLLM), running in its own container.

Implements `POST /transcribe` from the app's backend contract (see
`../docs/BACKEND.md`). No `WS /transcribe/stream` here — faster-whisper has
no equivalent to Qwen3-ASR's incremental-decoding API, so this backend
doesn't offer live streaming during recording. Point the app at the Qwen
backend instead if you want live cloud captions.

## Why this backend, alongside the Qwen one

- **Native timestamps, no chunking needed.** Unlike Qwen3-ASR (see
  `../backend/README.md`'s "Why chunk-based timestamps"), faster-whisper
  produces real segment-level `start`/`end` timestamps directly from a
  single `transcribe()` call, and handles long-form audio (30–90+ minute
  kajian recordings) internally — no manual chunking/overlap logic
  required in this backend's code at all.
- **Lighter, more shareable GPU footprint.** vLLM (the Qwen backend's
  serving engine) reserves a large fraction of total VRAM upfront
  regardless of the model's actual weight size. faster-whisper only holds
  what the model needs — around 3GB (`int8_float16`) to 6GB (`float16`)
  for large-v3 — making it realistic to run both backends on a single GPU
  at once if you want both models available, as long as the combined
  VRAM fits.
- **Different accuracy/language tradeoffs.** Whisper large-v3 is a
  well-established, heavily-benchmarked model; Qwen3-ASR is newer and
  scored better on some language-specific benchmarks per its own
  technical report. Worth having both to compare on your actual kajian
  content.

## Setup (Docker, recommended)

Requires a host with an NVIDIA GPU and the [NVIDIA Container
Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

```bash
cd backend-whisper
cp .env.example .env
# edit .env — at minimum set WHISPER_API_TOKEN if this will be reachable
# outside your homelab LAN, and WHISPER_COMPUTE_TYPE=int8_float16 if
# running alongside ../backend/'s Qwen container on the same GPU

docker compose up --build -d
docker compose logs -f   # first boot downloads ~3-6GB of model weights
```

Health check:

```bash
curl http://localhost:8082/health
# {"status":"ok","model":"large-v3","device":"cuda"}
```

Note the port: `8082`, distinct from `../backend/`'s `8080`/`8081`, so
both backends can run on the same host at once.

## Setup (plain Python, no Docker)

```bash
cd backend-whisper
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env  # edit as needed
export $(grep -v '^#' .env | xargs)
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

No system `ffmpeg` install needed — faster-whisper decodes audio via
PyAV, which bundles its own FFmpeg libraries (unlike the Qwen backend,
which shells out to a system `ffmpeg`).

## Running tests

Tests mock out the actual model (no GPU / faster-whisper install
required):

```bash
cd backend-whisper
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi "uvicorn[standard]" python-multipart pytest httpx
pytest -v
```

## Pointing the Flutter app at this backend

```bash
flutter run --dart-define=BACKEND_BASE_URL=http://<your-homelab-host>:8082
```

Then in the app's Settings, switch **Transcription** to **Cloud (Whisper
API)** — this time the label is accurate, since this backend really does
serve Whisper.

## Configuration reference

See `.env.example` for all settings. Key ones:

| Variable | Default | Notes |
|---|---|---|
| `WHISPER_MODEL_SIZE` | `large-v3` | Any faster-whisper model size, or a HF/CTranslate2 model id/path |
| `WHISPER_DEVICE` | `cuda` | `cuda` or `cpu` |
| `WHISPER_COMPUTE_TYPE` | `float16` | `int8_float16` roughly halves VRAM use with a small accuracy tradeoff — use this if sharing a GPU with the Qwen backend |
| `WHISPER_MAX_UPLOAD_BYTES` | `300MB` | Reject larger uploads with `413` |
| `WHISPER_API_TOKEN` | (empty) | Bearer token required on all requests if set |

## CUDA/cuDNN version note

`faster-whisper`'s own `requirements.txt` pins `ctranslate2>=4.0,<5`,
which targets **CUDA 12 + cuDNN 9** — the Dockerfile's base image
(`nvidia/cuda:12.3.2-cudnn9-runtime-ubuntu22.04`) matches this. If you
bump the `faster-whisper` version in `requirements.txt` later and it
pulls a different `ctranslate2` range, check
[faster-whisper's GPU install docs](https://github.com/SYSTRAN/faster-whisper#gpu)
for the currently compatible CUDA/cuDNN combination before changing this
image — this exact category of version mismatch caused a SIGILL crash
in the Qwen backend (see `../backend/README.md`'s troubleshooting
section) that took a while to track down.
