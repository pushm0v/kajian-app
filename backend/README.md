# Kajian App ASR backend

A self-hosted transcription backend for the Kajian App, running
[Qwen/Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B) via vLLM on
your own GPU (homelab, etc.) instead of a paid cloud STT API.

Implements `POST /transcribe` (batch, from the app's backend contract — see
`../docs/BACKEND.md`) and `WS /transcribe/stream` (live incremental
transcription, for real-time captions during recording). `POST /summarize`
(AI note generation) is not part of this service — the app falls back to
mock notes until that's built separately.

Runs entirely on vLLM, not the `transformers` backend, because vLLM is the
only backend Qwen3-ASR's live-streaming API supports — see "Live streaming"
below. Both endpoints share the one loaded model instance.

## Why chunk-based timestamps, not word-level (batch endpoint)

Qwen3-ASR-1.7B outputs plain transcribed text only — it has no built-in
timestamps. Real per-word timing requires a second model,
`Qwen3-ForcedAligner-0.6B`, which officially supports only 11 languages
(Chinese, English, Cantonese, French, German, Italian, Japanese, Korean,
Portuguese, Russian, Spanish) — **not Indonesian or Arabic**, which is this
app's primary use case (Indonesian lectures with embedded Arabic Quran/Hadith
quotes).

Rather than depend on an aligner that doesn't officially support our
languages, `POST /transcribe` transcribes audio in fixed-size chunks (30s by
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

## Live streaming (`WS /transcribe/stream`)

Qwen3-ASR's vLLM backend has a genuine incremental-decoding API
(`init_streaming_state` / `streaming_transcribe` / `finish_streaming_transcribe`)
— this isn't chunked-batch dressed up as streaming; audio segments as short
as ~500ms produce updated partial output. This comes with a documented
accuracy tradeoff vs. the batch path: the model's own benchmarks show
streaming mode has measurably worse WER than offline mode (e.g. 1.7B: 3.33
avg WER streaming vs. 2.69 offline). Use this for live captions during
recording; keep relying on `POST /transcribe` after recording for the
accurate final transcript.

### Wire protocol

Connect to `ws://<host>:8080/transcribe/stream?locale=id_ID` (add
`&token=...` if `ASR_API_TOKEN` is set — bearer headers don't apply cleanly
to WebSocket handshakes in most client libraries, so auth here is a query
param instead).

- **Client → server:** binary frames of raw **PCM16LE mono audio at
  16kHz** — exactly what Flutter's `record` package's `startStream()`
  produces when configured with `AudioEncoder.pcm16bits`,
  `sampleRate: 16000`, `numChannels: 1`. Any frame size works; the server
  buffers until it has enough audio for one `ASR_STREAM_CHUNK_SIZE_SEC`
  decode step. Send a text frame containing exactly `__end__` when done.
- **Server → client:** JSON text frames:
  - `{"type": "partial", "text": "..."}` — the **cumulative** transcript so
    far (not a delta from the last message), sent after each decode step.
  - `{"type": "final", "text": "..."}` — sent once, after `__end__`, then
    the server closes the connection.
  - `{"type": "error", "message": "..."}` — on failure.

### Streaming tuning (`init_streaming_state` kwargs)

These map directly to `qwen_asr`'s `init_streaming_state(...)` parameters —
defaults match the official Qwen3-ASR streaming example:

| Variable | Default | Meaning |
|---|---|---|
| `ASR_STREAM_CHUNK_SIZE_SEC` | `2.0` | Audio duration that triggers each incremental decode step |
| `ASR_STREAM_UNFIXED_CHUNK_NUM` | `2` | How many initial chunks get a full re-decode ("unstable" phase) before the model starts reusing previously-decoded text as a prefix |
| `ASR_STREAM_UNFIXED_TOKEN_NUM` | `5` | Once past that phase, how many trailing tokens are rolled back from the accumulated text before reusing it as a prefix — reduces flicker/jitter right at chunk boundaries |

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

### Troubleshooting: container restarts in a loop right after "Loading ... via vLLM"

If the logs show the CUDA banner and the "Loading" message repeating
forever with no Python error in between, vLLM is almost certainly
crashing on the container's shared-memory limit. vLLM's worker
processes communicate over `/dev/shm`, and Docker's default there is
only 64MB — nowhere near enough for a 1.7B model's tensor buffers.
`docker-compose.yml` sets `shm_size: "8gb"` to fix this; if you're
running the container directly (not via compose), add `--shm-size=8g`
to your `docker run` command instead.

## Setup (plain Python, no Docker)

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt  # pulls vLLM + a compatible torch build automatically

cp .env.example .env  # edit as needed
export $(grep -v '^#' .env | xargs)  # load .env into the shell
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

`ffmpeg` must be on `PATH` (used to decode the app's `.m4a` recordings to
16kHz mono PCM for the batch endpoint) — install via your OS package
manager if not already present.

## Running tests

Tests mock out the actual model (no GPU / vLLM / `qwen-asr` install
required):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi "uvicorn[standard]" python-multipart numpy pytest httpx websockets
pytest -v
```

## Pointing the Flutter app at this backend

```bash
flutter run --dart-define=BACKEND_BASE_URL=http://<your-homelab-host>:8080
```

Then in the app's Settings, switch **Transcription** to **Cloud (Whisper
API)** — the label is a holdover from the original design doc; this backend
serves the same `/transcribe` contract using Qwen3-ASR instead of Whisper.
Live streaming (`/transcribe/stream`) isn't wired into the Flutter app yet
as of this writing — the app-side client and a settings toggle to enable it
still need to be built separately.

If you set `ASR_API_TOKEN` in `.env`, the app has no way to send it yet on
the batch `/transcribe` path (there's no bearer-token setting on the
Flutter side) — leave the token unset for LAN-only use, or add app-side
auth support before exposing this server past your homelab network.

## Configuration reference

See `.env.example` for all settings. Key ones:

| Variable | Default | Notes |
|---|---|---|
| `ASR_MODEL_ID` | `Qwen/Qwen3-ASR-1.7B` | Set to `Qwen/Qwen3-ASR-0.6B` for lower VRAM use |
| `ASR_GPU_MEMORY_UTILIZATION` | `0.8` | Fraction of GPU memory vLLM may reserve |
| `ASR_CHUNK_SECONDS` | `30` | Batch endpoint: smaller = more granular timestamps, more model calls |
| `ASR_MAX_UPLOAD_BYTES` | `300MB` | Reject larger uploads with `413` |
| `ASR_API_TOKEN` | (empty) | Required on `/transcribe` (header) and `/transcribe/stream` (query param) if set |
| `ASR_STREAM_CHUNK_SIZE_SEC` | `2.0` | Streaming endpoint: seconds of audio per incremental decode step |
