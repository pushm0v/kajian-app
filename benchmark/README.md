# ASR backend benchmark

Compare the two self-hosted transcription backends — **Qwen3-ASR** (`../backend/`)
and **Whisper large-v3** (`../backend-whisper/`) — on the *same* audio, and get
objective speed + accuracy numbers so you can decide which to ship (or when to
use each).

It talks to the exact same `POST /transcribe` contract the app uses, so you're
measuring the real production path.

## Install

```bash
cd benchmark
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # just `requests`
# optional, for audio-duration fallback: install ffmpeg (provides ffprobe)
```

## Run

```bash
python compare_backends.py \
  --qwen    http://<gpu-host>:8000 \
  --whisper http://<gpu-host>:8001 \
  --audio ./samples \
  --locale id_ID \
  --repeat 3 \
  --out report.md --csv rows.csv
```

- `--audio` takes files, globs, or a folder (any of `.m4a .mp3 .wav .aac .ogg
  .flac .webm .mp4`). Use real kajian clips of varying length for a meaningful
  read.
- `--repeat N` sends each file N times per backend and reports the **best**
  wall latency (warms caches, reduces noise).
- `--token` (or `ASR_API_TOKEN` env) if your backends enforce a bearer token.
- `--backend NAME=URL` to add more than two backends.

### Getting real accuracy (WER/CER)

Speed is measured automatically. **Accuracy needs ground truth.** Put a plain-text
reference transcript next to each clip's basename and pass `--refs`:

```
samples/kajian01.m4a
refs/kajian01.txt        # what was *actually* said, hand-corrected
```
```bash
python compare_backends.py --qwen … --whisper … --audio samples --refs refs
```

Even 3–5 carefully transcribed clips give a solid WER signal. Without `--refs`
you still get speed plus a **cross-model disagreement** number (how much the two
models differ), which flags hard audio but isn't a substitute for real accuracy.

## What the metrics mean

| Metric | Meaning | Better |
| --- | --- | --- |
| **wall ms** | Client round-trip: upload + inference + download. Includes your network. | lower |
| **server ms** | Pure inference time reported by the backend (`processing_ms`). Network-independent — the fair speed number. | lower |
| **×realtime** | `audio_seconds / inference_seconds`. 30× means a 60s clip transcribes in ~2s. | higher |
| **WER** | Word Error Rate vs the reference (edits ÷ reference words). | lower |
| **CER** | Character Error Rate — more forgiving of word-boundary/spelling nits. | lower |

Text is normalized before scoring: NFC, lowercased, Arabic harakat/tatweel and
punctuation stripped, whitespace collapsed — so neither model is penalized for
diacritics or punctuation style.

## Fairness notes

- **Run each backend on its own GPU** (or one at a time) for clean speed numbers.
  If both share a single GPU, concurrent load makes them contend; this harness
  calls them **sequentially** per file to avoid that.
- Prefer **server ms / ×realtime** over wall ms when comparing the *models* —
  wall ms also reflects however far each host is from you.
- Use a **spread of clip lengths** (30s, 5min, 30min+). Qwen chunks manually;
  Whisper does long-form natively — their relative speed can change with length.
- The backends report `audio_seconds` from the last segment end. With Whisper's
  VAD trimming trailing silence, ×realtime is computed over *speech* duration,
  which is what you care about.

## Output

- `report.md` — summary table, a **verdict** (fastest / most accurate), and a
  per-file breakdown.
- `rows.csv` — raw per-(file,backend) rows for your own plots/pivots.
- `--dump <dir>` — optionally writes each model's transcript to
  `<clip>.<backend>.txt` for eyeballing quality side by side.

## Also: comparing inside the app

This harness is for batch, offline evaluation. If you also want an in-app
"record once → see both models side by side" mode (great for collecting human
preference on real kajian), say so — the backends already expose everything
needed; it's a `ModelComparisonService` that fans one recording out to both
`/transcribe` URLs plus a compare screen.
