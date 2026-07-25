# backend-core dev console

A single self-contained HTML page for exercising `backend-core` directly —
no Flutter, no build step, no dependencies. Useful for testing the backend
in isolation: upload an audio file and run it through transcribe +
summarize, or stream live mic audio through the same WebSocket proxy the
app uses for live captions.

## Running it

`backend-core` must already be running (see `../README.md`) with
`CORE_DEV_AUTH_BYPASS=true` so any string works as an auth token — no real
Firebase sign-in needed for local testing.

Serve this folder over plain HTTP (opening `index.html` directly via
`file://` will not work — `getUserMedia`/`AudioWorklet` for live mic
streaming require a real HTTP(S) origin):

```bash
cd backend-core/dev-console
python3 -m http.server 8091
# open http://localhost:8091
```

Then in the page:

1. **Connection** — set the backend-core base URL (default assumes
   `docker compose up` on port 8090) and an auth token. With dev bypass on,
   any string becomes a stable Firebase-UID stand-in; the same string
   always maps to the same auto-provisioned user. Click **Check /health**
   to confirm connectivity and see which user you're signed in as.
2. **Session** — creates a session row to attach audio/transcript/notes to.
3. **Upload + transcribe** — picks a local audio file, walks through the
   real presigned-upload-URL flow (mint URL → PUT directly to MinIO/S3 →
   confirm → transcribe), and shows the resulting segments. Requires the
   ASR worker you pick (`qwen`/`whisper`) to actually be reachable at
   `QWEN_BACKEND_URL`/`WHISPER_BACKEND_URL`.
4. **Summarize** — runs `/summarize` against the transcript from step 3.
   Requires `ANTHROPIC_API_KEY` to be set on the server.
5. **Live mic streaming** — records from your browser's microphone, downmixes
   to PCM16LE mono 16kHz in an `AudioWorklet` (matching what the Flutter
   app's `record` package produces), and streams it to
   `WS /transcribe/stream` for live captions. Requires `QWEN_BACKEND_URL`
   (only the Qwen worker supports streaming) and mic permission in your
   browser.

Everything logs to the **Log** panel at the bottom, including the exact
failure reason for any HTTP error — useful for seeing backend-core's real
error responses (e.g. a 503 when an ASR worker isn't configured, or a 502
if `/summarize` can't reach Anthropic).

## What this isn't

Not a general admin UI (that's `../../admin/`) and not meant to be
deployed anywhere — it's a local development/testing aid for backend-core
itself, so you can validate the API without needing the Flutter app or a
real Firebase account.
