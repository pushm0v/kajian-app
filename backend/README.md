# Kajian App ASR backend

A self-hosted transcription backend for the Kajian App, running
[Qwen/Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) on your own
GPU (homelab, etc.) instead of a paid cloud STT API.

Implements only `POST /transcribe` from the app's backend contract (see
`../docs/BACKEND.md`). `POST /summarize` (AI note generation) is not part of
this service — the app falls back to mock notes until that's built
separately.

## Why chunk-based timestamps, not word-level

Qwen3-ASR-1.7B outputs plain transcribed text only — it has no built-in
timestamps. Real per-word timing requires a second model,
`Qwen3-ForcedAligner-0.6B`, which officially supports only 11 languages
(Chinese, English, Cantonese, French, German, Italian, Japanese, Korean,
Portuguese, Russian, Spanish) — **not Indonesian or Arabic**, which is this
app's primary use case (Indonesian lectures with embedded Arabic Quran/Hadith
quotes).

Rather than depend on an aligner that doesn't officially support our
languages, this backend transcribes audio in fixed-size chunks (30s by
default, configurable via `ASR_CHUNK_SECONDS`) and reports each chunk's
boundaries as its segment's `startMs`/`endMs`. This means:

- Segments are chunk-granularity, not word-level — good enough for the
  app's transcript view and scrubbing, not sample-accurate captions.
- Chunking is also required regardless of timestamps, since Qwen3-ASR
  documents a ~20-minute limit per call and kajian recordings can run
  30–90+ minutes.
- Consecutive chunks overlap slightly (`ASR_CHUNK_OVERLAP_SECONDS`, default
  1s) in the audio actually sent to the model, to reduce words getting cut
  off right at a chunk boundary — but the *reported* timestamps still tile
  the recording exactly with no gaps or double-counted spans.

If you later want real word-level timestamps, the cleanest path is probably
a separate CTC-based forced aligner that does support Indonesian/Arabic
(e.g. a wav2vec2-based one), run as a second pass over the merged
transcript — this backend doesn't attempt that.

## Setup (Docker, recommended)

Requires a host with an NVIDIA GPU (6GB+ VRAM comfortably runs the 1.7B
model) and the [NVIDIA Container
Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
installed so Docker can access the GPU.

```bash
cd backend
cp .env.example .env
# edit .env — at minimum set ASR_API_TOKEN if this will be reachable
# outside your homelab LAN

docker compose up --build -d
docker compose logs -f   # first boot downloads ~4.7GB of model weights
```

Health check:

```bash
curl http://localhost:8080/health
# {"status":"ok","model":"Qwen/Qwen3-ASR-1.7B","device":"cuda"}
```

## Setup (plain Python, no Docker)

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install torch --index-url https://download.pytorch.org/whl/cu124  # match your CUDA version
pip install -r requirements.txt

cp .env.example .env  # edit as needed
export $(grep -v '^#' .env | xargs)  # load .env into the shell
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

`ffmpeg` must be on `PATH` (used to decode the app's `.m4a` recordings to
16kHz mono PCM) — install via your OS package manager if not already
present.

## Running tests

Tests mock out the actual model (no GPU / `qwen-asr` install required):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest httpx
pytest -v
```

## Pointing the Flutter app at this backend

```bash
flutter run --dart-define=BACKEND_BASE_URL=http://<your-homelab-host>:8080
```

Then in the app's Settings, switch **Transcription** to **Cloud (Whisper
API)** — the label is a holdover from the original design doc; this backend
serves the same `/transcribe` contract using Qwen3-ASR instead of Whisper.

If you set `ASR_API_TOKEN` in `.env`, the app has no way to send it yet
(there's no bearer-token setting on the Flutter side) — leave the token
unset for LAN-only use, or add app-side auth support before exposing this
server past your homelab network.

## Configuration reference

See `.env.example` for all settings. Key ones:

| Variable | Default | Notes |
|---|---|---|
| `ASR_MODEL_ID` | `Qwen/Qwen3-ASR-1.7B` | Set to `Qwen/Qwen3-ASR-0.6B` for lower VRAM use |
| `ASR_DEVICE` | `auto` | `cuda`, `cpu`, or `auto`-detect |
| `ASR_CHUNK_SECONDS` | `30` | Smaller = more granular timestamps, more model calls |
| `ASR_MAX_UPLOAD_BYTES` | `300MB` | Reject larger uploads with `413` |
| `ASR_API_TOKEN` | (empty) | Bearer token required on all requests if set |
