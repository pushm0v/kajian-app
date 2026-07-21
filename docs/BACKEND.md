# Backend proxy

**Why a backend?** Shipping an Anthropic or OpenAI API key inside the mobile app
is insecure — anyone can extract it from the app bundle and run up your bill. The
app is designed to talk to a small backend that holds the secret keys and exposes
two endpoints. Point the app at it with:

```bash
flutter run --dart-define=BACKEND_BASE_URL=https://api.yourdomain.com
```

With no `BACKEND_BASE_URL` set, the app runs in **mock mode** — cloud
transcription and AI notes return realistic sample data so you can build and demo
the whole flow without any backend.

> **Self-hosted transcription options:** two ready-to-run `POST /transcribe`
> implementations exist, each in its own container so you can run either
> (or both, on a single shared GPU) independently:
> - `../backend/` — [Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)
>   via vLLM. Also offers `WS /transcribe/stream` for live captions during
>   recording. See `backend/README.md`.
> - `../backend-whisper/` — Whisper large-v3 via
>   [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Lighter
>   VRAM footprint, native segment timestamps, no live-streaming endpoint.
>   See `backend-whisper/README.md`.
>
> Neither implements `/summarize`; pair either with your own summarize
> backend or leave that endpoint unconfigured.

## Contract

### `POST /transcribe`
Multipart form: `audio` (file), `locale` (e.g. `id_ID`), `model` (`whisper-1`).

Response:
```json
{
  "segments": [
    { "id": "0", "text": "Alhamdulillah…", "startMs": 0, "endMs": 8000, "isFinal": true }
  ]
}
```

### `POST /summarize`
JSON body: `{ "transcript": "…", "title": "…", "model": "claude-sonnet-5" }`

Response: a `KajianNote` JSON object:
```json
{
  "summary": "…",
  "keyPoints": ["…"],
  "topics": ["…"],
  "references": [{ "type": "quran", "citation": "Al-Baqarah: 153", "note": "…" }],
  "actionItems": ["…"]
}
```

## Minimal reference implementation (Node / Express)

```js
import express from "express";
import multer from "multer";
import fs from "node:fs";
import Anthropic from "@anthropic-ai/sdk";
import OpenAI from "openai";

const app = express();
app.use(express.json({ limit: "2mb" }));
const upload = multer({ dest: "/tmp" });
const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });
const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

// 1) Transcription via Whisper
app.post("/transcribe", upload.single("audio"), async (req, res) => {
  try {
    const tr = await openai.audio.transcriptions.create({
      file: fs.createReadStream(req.file.path),
      model: "whisper-1",
      language: (req.body.locale || "id_ID").split("_")[0],
      response_format: "verbose_json",
      timestamp_granularities: ["segment"],
    });
    const segments = (tr.segments || []).map((s, i) => ({
      id: String(i),
      text: s.text.trim(),
      startMs: Math.round(s.start * 1000),
      endMs: Math.round(s.end * 1000),
      isFinal: true,
    }));
    res.json({ segments });
  } catch (e) {
    res.status(500).json({ error: String(e) });
  } finally {
    if (req.file) fs.unlink(req.file.path, () => {});
  }
});

// 2) Structured notes via Claude
const SYSTEM = `You turn an Islamic lecture (kajian) transcript into study notes.
The transcript may mix Indonesian, Malay, English and Arabic. Preserve Arabic
terms and Quran/Hadith citations. Respond ONLY with a JSON object matching:
{ "summary": string, "keyPoints": string[], "topics": string[],
  "references": [{"type":"quran"|"hadith","citation":string,"note":string|null}],
  "actionItems": string[] }`;

app.post("/summarize", async (req, res) => {
  try {
    const msg = await anthropic.messages.create({
      model: req.body.model || "claude-sonnet-5",
      max_tokens: 1500,
      system: SYSTEM,
      messages: [{
        role: "user",
        content: `Kajian title: ${req.body.title || "(untitled)"}\n\nTranscript:\n${req.body.transcript}`,
      }],
    });
    const text = msg.content.find((b) => b.type === "text")?.text ?? "{}";
    const json = JSON.parse(text.replace(/^```json\s*|\s*```$/g, ""));
    res.json(json);
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
});

app.listen(8080, () => console.log("kajian backend on :8080"));
```

> Add authentication (per-user token) before going to production so only your
> app's users can call these endpoints.

## Model options for `/summarize`

| Model             | Use when                                  |
| ----------------- | ----------------------------------------- |
| `claude-opus-4-8` | Highest quality, long/complex lectures    |
| `claude-sonnet-5` | Balanced quality/cost — the app default   |
| `claude-haiku-4-5-20251001` | Cheapest, fastest, short kajian |
