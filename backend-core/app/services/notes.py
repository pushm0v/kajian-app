"""Generates structured kajian notes from a transcript via the Anthropic
API. This is the server-side implementation of the /summarize contract the
Flutter app's AiNotesService already speaks (see docs/BACKEND.md in the
Flutter repo) — the system prompt and response schema here are copied
verbatim from lib/services/ai_notes_service.dart's dev-only direct-call
path, now made real and holding the API key server-side instead of never
being implemented.
"""

from __future__ import annotations

import json
import re

import anthropic

from .. import config

_SYSTEM_PROMPT = """\
You are an assistant that turns a transcript of an Islamic lecture (kajian) into
concise, well-structured study notes. The transcript may mix Indonesian, Malay,
English and Arabic. Preserve Arabic terms and any Quran/Hadith citations
faithfully. Respond ONLY with a single JSON object, no prose, matching:
{
  "summary": string,               // 1-2 sentence overview
  "keyPoints": string[],           // main teaching points, in order
  "topics": string[],              // short thematic tags
  "references": [                  // Quran/Hadith mentioned
    { "type": "quran"|"hadith", "citation": string, "note": string|null }
  ],
  "actionItems": string[]          // practical takeaways for the listener
}"""

_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")


def _extract_json(raw: str) -> dict:
    """Tolerant JSON extraction — mirrors the app's own
    AiNotesService._extractJson, in case the model wraps its answer in a
    fenced code block or adds stray prose despite the system prompt."""
    s = raw.strip()
    m = _FENCE_RE.search(s)
    if m:
        s = m.group(1).strip()
    start, end = s.find("{"), s.rfind("}")
    if start >= 0 and end > start:
        s = s[start : end + 1]
    return json.loads(s)


def generate(transcript: str, title: str | None, model: str | None = None) -> dict:
    if not transcript.strip():
        return {
            "summary": "",
            "keyPoints": [],
            "topics": [],
            "references": [],
            "actionItems": [],
        }

    message = _client.messages.create(
        model=model or config.DEFAULT_NOTES_MODEL,
        max_tokens=1500,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Kajian title: {title or '(untitled)'}\n\n"
                f"Transcript:\n{transcript}",
            }
        ],
    )
    text = next(
        (block.text for block in message.content if block.type == "text"), "{}"
    )
    return _extract_json(text)
