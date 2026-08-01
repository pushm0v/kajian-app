# Kajian App — Notes Backend

Self-hosted LLM that turns a kajian transcript into structured study notes
(summary, key points, topics, Quran/Hadith references, action items).

Replaces the Anthropic API call that used to live in
`backend-core/app/services/notes.py`. No external API key, and transcripts
never leave the host — which matters for recordings of private study
circles.

## Model

**`Qwen/Qwen2.5-7B-Instruct-AWQ`** — 4-bit, ~5.5GB of weights.

Chosen for this job rather than general benchmark standing. The prompt
demands two things a small model can easily fail at: strict JSON-only
output, and faithful handling of Indonesian/Malay/English/Arabic in one
transcript while preserving Quran and Hadith citations. Qwen2.5's instruct
tuning covers all four languages and holds a JSON schema well at low
temperature; the Llama-3.1 family at this size is weaker on Indonesian and
markedly weaker on Arabic script.

AWQ specifically (not GPTQ/GGUF) because vLLM has first-class AWQ kernels,
and 4-bit is what makes this fit alongside the speaker embedding service
on a single 12GB card.

### Quality expectations

**This is meaningfully weaker than Claude was.** A 7B at 4-bit will:

- occasionally wrap its JSON in ``` fences or add prose (handled — see
  `_extract_json`)
- emit references as bare strings rather than objects (handled — see
  `_coerce`)
- **paraphrase or mis-cite Quran/Hadith references more often**

That last one is not handled, because it can't be: the model either
recalls a citation correctly or it doesn't. Treat generated references as
prompts to verify, not as authoritative. If citation fidelity turns out to
matter more than self-hosting, `backend-core`'s notes proxy is a thin HTTP
client — pointing it back at a hosted model is a small change.

## GPU layout

| Device | Service | VRAM |
|---|---|---|
| 0 | **this service** + `../backend-embedding/` | ~6.6GB reserved + on-demand |
| 1 | `../backend-whisper/` (large-v3, fp16) | ~11.6GB of 12GB |

`NOTES_GPU_MEMORY_UTILIZATION` defaults to **0.55**, well below the 0.8 the
ASR backend uses. vLLM reserves its share upfront and never releases it,
while the embedding service's ONNX Runtime CUDA session allocates on
demand (a ~28MB model still wanted ~2.75GB of workspace — the CUDA EP
over-allocates for small models). Leaving ~45% free is what keeps
embedding able to run at all.

**`../backend/` (Qwen/vLLM ASR) must stay stopped.** At its 0.8
reservation there is no room on device 0 for either of these services.

## Running

```bash
cp .env.example .env
docker compose up -d --build
curl localhost:8084/health
```

First boot downloads ~5.5GB of weights, then vLLM's engine startup (eager
mode) takes another minute or two — the healthcheck allows 10 minutes.

Then point `backend-core` at it:

```bash
# backend-core/.env
NOTES_BACKEND_URL=http://localhost:8084
```

Leaving that **empty switches notes off entirely** — sessions still
transcribe, and the app shows "notes unavailable" rather than failing (see
`backend-core`'s `NotesUnavailable`).

## API

### `GET /health`

```json
{"status": "ok", "model": "Qwen/Qwen2.5-7B-Instruct-AWQ", "quantization": "awq"}
```

### `POST /summarize`

```json
{"transcript": "...", "title": "Kajian Sabar"}
```

Returns `backend-core`'s exact `KajianNote` shape:

```json
{
  "summary": "...",
  "keyPoints": ["..."],
  "topics": ["..."],
  "references": [{"type": "quran", "citation": "2:153", "note": null}],
  "actionItems": ["..."]
}
```

**503** while the model is loading — `backend-core` maps that to "notes
unavailable" and leaves the session at `transcribed` rather than failing
it, so a restart mid-session degrades gracefully.
**500** when the model returns unparseable output — a genuine failure,
since retrying won't help.

Set `NOTES_API_TOKEN` to require `Authorization: Bearer <token>`; it must
match `backend-core`'s `NOTES_BACKEND_TOKEN`.

## Tests

```bash
pip install pytest fastapi httpx
python -m pytest tests/ -q
```

vLLM is imported lazily, so the suite runs without a GPU or the package.
It covers JSON extraction and schema coercion — the parts most likely to
break on real model output.
