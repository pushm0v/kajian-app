"""Loads the notes LLM once at startup via vLLM and turns kajian
transcripts into structured study notes.

The system prompt and response schema below are copied VERBATIM from
backend-core/app/services/notes.py, which sent them to Anthropic. That's
deliberate: this service is a drop-in replacement for that call, so the
JSON it returns must satisfy exactly the same contract backend-core
already parses and persists (see its KajianNote/ScriptureReference
models). Changing the schema here without changing it there breaks notes
silently — the .get() defaults on the parsing side would just yield empty
fields.

vLLM is called in-process via vllm.LLM(...) rather than by running its
OpenAI-compatible server and talking HTTP to it, matching what
../backend/app/asr_model.py does. One less moving part, and this service
has exactly one endpoint.
"""

from __future__ import annotations

import json
import logging
import re
import threading

from . import config

logger = logging.getLogger("kajian_notes")

# Copied verbatim from backend-core/app/services/notes.py — see module
# docstring. Keep in sync.
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

_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)```")

_EMPTY_NOTES = {
    "summary": "",
    "keyPoints": [],
    "topics": [],
    "references": [],
    "actionItems": [],
}


def _extract_json(raw: str) -> dict:
    """Tolerant JSON extraction — mirrors backend-core's own _extract_json
    (and the app's AiNotesService._extractJson), in case the model wraps
    its answer in a fenced code block or adds stray prose despite the
    system prompt. A local 7B does this noticeably more often than Claude
    did, which is exactly why this tolerance is worth keeping."""
    s = raw.strip()
    m = _FENCE_RE.search(s)
    if m:
        s = m.group(1).strip()
    start, end = s.find("{"), s.rfind("}")
    if start >= 0 and end > start:
        s = s[start : end + 1]
    return json.loads(s)


def _coerce(data: dict) -> dict:
    """Forces the model's output into the exact shape backend-core expects.

    A 7B model at 4-bit will occasionally return a string where the schema
    says list, omit a key, or emit a reference with a missing `type`.
    backend-core's parsing uses .get() defaults, so a wrong *type* (rather
    than a missing key) would raise there instead of degrading — normalise
    it here, where the model's quirks are known, rather than letting a
    malformed field surface as a 500 two services away.
    """
    def as_list(value) -> list:
        if isinstance(value, list):
            return [v for v in value if v not in (None, "")]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    references = []
    for ref in as_list(data.get("references")):
        if not isinstance(ref, dict):
            # Some outputs give a bare citation string instead of an object.
            if isinstance(ref, str):
                references.append({"type": "quran", "citation": ref, "note": None})
            continue
        ref_type = str(ref.get("type", "quran")).lower()
        references.append({
            "type": ref_type if ref_type in ("quran", "hadith") else "quran",
            "citation": str(ref.get("citation", "")),
            "note": ref.get("note"),
        })

    summary = data.get("summary", "")
    return {
        "summary": summary if isinstance(summary, str) else str(summary),
        "keyPoints": [str(v) for v in as_list(data.get("keyPoints"))],
        "topics": [str(v) for v in as_list(data.get("topics"))],
        "references": [r for r in references if r["citation"]],
        "actionItems": [str(v) for v in as_list(data.get("actionItems"))],
    }


class NotesModelWrapper:
    """Thread-safe wrapper around a single loaded vLLM engine. Mirrors the
    load()/lock/singleton shape of ../backend-whisper/app/asr_model.py."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._llm = None
        self._tokenizer = None

    def load(self) -> None:
        if self._llm is not None:
            return

        logger.info(
            "Loading notes model %s (quantization=%s, gpu_mem=%.2f, max_len=%d, eager=%s) ...",
            config.MODEL_ID, config.QUANTIZATION, config.GPU_MEMORY_UTILIZATION,
            config.MAX_MODEL_LEN, config.ENFORCE_EAGER,
        )
        # Imported lazily so config-only tooling and the test suite don't
        # need vllm/torch installed (matches asr_model.py's pattern).
        from vllm import LLM  # noqa: PLC0415

        llm = LLM(
            model=config.MODEL_ID,
            quantization=config.QUANTIZATION,
            gpu_memory_utilization=config.GPU_MEMORY_UTILIZATION,
            max_model_len=config.MAX_MODEL_LEN,
            enforce_eager=config.ENFORCE_EAGER,
            dtype="float16",
        )
        with self._lock:
            self._llm = llm
            self._tokenizer = llm.get_tokenizer()
        logger.info("Notes model loaded.")

    @property
    def is_loaded(self) -> bool:
        return self._llm is not None

    def _truncate(self, transcript: str) -> str:
        """Trims a transcript that would overflow the context window.

        Keeps the head: a kajian states its topic and main argument early,
        and the prompt asks for a summary and key points "in order", so the
        opening carries more of what the notes need than the closing does.
        Budget leaves room for the system prompt and the generated notes.
        """
        if self._tokenizer is None:
            return transcript
        budget = config.MAX_MODEL_LEN - config.MAX_TOKENS - 512
        ids = self._tokenizer.encode(transcript)
        if len(ids) <= budget:
            return transcript
        logger.warning(
            "Transcript is %d tokens, truncating to %d (notes will cover "
            "the earlier part of the lecture only)", len(ids), budget,
        )
        return self._tokenizer.decode(ids[:budget])

    def generate(self, transcript: str, title: str | None) -> dict:
        """Returns structured notes for `transcript`, in backend-core's
        schema. An empty transcript yields empty notes rather than an
        error, matching what backend-core's own generate() did."""
        if self._llm is None:
            raise RuntimeError("NotesModelWrapper.load() must be called before use")
        if not transcript.strip():
            return dict(_EMPTY_NOTES)

        from vllm import SamplingParams  # noqa: PLC0415

        prompt = self._tokenizer.apply_chat_template(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Kajian title: {title or '(untitled)'}\n\n"
                    f"Transcript:\n{self._truncate(transcript)}",
                },
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
        params = SamplingParams(
            temperature=config.TEMPERATURE,
            max_tokens=config.MAX_TOKENS,
        )

        # vLLM's generate() is not documented as thread-safe and this
        # engine is a single shared instance; serialise calls rather than
        # risk interleaved scheduling. Notes run once per session, so
        # there's no throughput cost worth optimising here.
        with self._lock:
            outputs = self._llm.generate([prompt], params)

        raw = outputs[0].outputs[0].text
        try:
            return _coerce(_extract_json(raw))
        except (json.JSONDecodeError, ValueError) as e:
            # Surfaced as a 500 by main.py. backend-core treats that as a
            # genuine failure (not "unavailable"), which is right: retrying
            # later won't help if the model reliably can't produce JSON for
            # this transcript.
            logger.error("Model did not return usable JSON: %s | raw=%r", e, raw[:500])
            raise ValueError(f"Model did not return valid JSON: {e}") from e


# Module-level singleton, initialized at FastAPI startup (see main.py).
model = NotesModelWrapper()
