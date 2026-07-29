# Kajian App — Speaker Embedding Backend

A dedicated GPU service that extracts a 192-dim voice fingerprint from a
recording, used by `backend-core` to suggest which known speaker a session
belongs to (see its `services/speaker_matching.py`).

## Why this is its own service

This ran inside `../backend-whisper/` originally. Sharing that card forced
the embedding step onto CPU: Whisper large-v3 at float16 was measured
(`nvidia-smi`) using **~11.6GB of that 12GB card**, leaving too little
headroom for ONNX Runtime's CUDA execution provider — a ~27MB model still
wanted ~2.75GB for a single Conv node's workspace, a known CUDA EP
over-allocation pattern for small models. CPU extraction took a measured
**~93s for a 44-minute recording**.

On its own GPU that constraint disappears, and the two services can be
restarted and version-bumped independently.

## Model choice

Two checkpoints are baked into the image, switchable via `EMBEDDING_MODEL`
or per-request:

| Key | Checkpoint | Size | Languages |
|---|---|---|---|
| `campplus` (default) | 3D-Speaker CAM++ | ~28MB | zh + **en** |
| `eres2netv2` | 3D-Speaker ERes2NetV2 | ~71MB | zh-cn only |

`campplus` is the default because it is the **only multilingual
checkpoint in sherpa-onnx's entire speaker-recognition zoo** — every
ERes2Net/ERes2NetV2 variant there is zh-cn monolingual, and the remaining
options (WeSpeaker, NeMo TitaNet) are English/VoxCeleb only. That matters
here: this app transcribes Indonesian kajian audio with Arabic quotation,
and SVeritas benchmark data shows 8–23 point EER degradation on
cross-language trials for monolingual models.

`eres2netv2` is a stronger architecture with better scores *on Chinese*.
Whether that advantage survives the transfer to Indonesian is an open
empirical question, so both ship in the image — A/B them on real
recordings via the dev-console's model dropdown rather than picking on
benchmark reputation.

## Running

```bash
cp .env.example .env      # adjust as needed
docker compose up -d --build
curl localhost:8083/health
```

**GPU device 0** is reserved in `docker-compose.yml` — the card previously
held by `../backend/`'s Qwen/vLLM worker. vLLM reserves VRAM upfront, so
**that container must be stopped** before this one can use CUDA. Device 1
stays dedicated to `../backend-whisper/`.

Set `EMBEDDING_PROVIDER=cpu` (or pass `provider=cpu` per-request) to run
without a GPU at all — the same wheel serves both.

## API

### `GET /health`

```json
{"status": "ok", "model": "campplus", "model_path": "...", "provider": "cuda"}
```

### `POST /embed-speaker`

Multipart form:

| Field | Required | Description |
|---|---|---|
| `audio` | yes | The recording (any ffmpeg-readable format) |
| `provider` | no | `cpu` / `cuda` — overrides the configured default |
| `model` | no | `campplus` / `eres2netv2` — overrides the configured default |

```json
{"embedding": [...], "dim": 192, "processing_ms": 1234, "provider": "cuda", "model": "campplus"}
```

Overriding `provider`/`model` reloads the extractor (a few seconds,
one-time) and persists for subsequent calls until changed again.

Set `EMBEDDING_API_TOKEN` to require `Authorization: Bearer <token>`; it
must match `backend-core`'s `EMBEDDING_BACKEND_TOKEN`.

## Tests

```bash
pip install fastapi uvicorn python-multipart anyio numpy pytest httpx
python -m pytest tests/ -q
```

sherpa-onnx is mocked out, so the suite runs without a GPU or the wheel.
