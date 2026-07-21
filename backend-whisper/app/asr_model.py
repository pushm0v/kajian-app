"""Loads Whisper large-v3 once at startup via faster-whisper (CTranslate2),
and exposes a single transcribe(...) call that returns native
segment-level timestamps.

Unlike the Qwen3-ASR backend (../backend/), no manual audio chunking is
needed here: faster-whisper handles long-form audio (30-90+ minute kajian
recordings) natively via CTranslate2's sliding-window decoding, and
produces real per-segment start/end timestamps out of the box — no
chunk-boundary approximation required.

API surface used (faster_whisper.WhisperModel, confirmed against the
package's README/source):
  - WhisperModel(model_size_or_path, device=, compute_type=,
      download_root=) -> loads the model
  - .transcribe(audio, language=, vad_filter=) -> (segments, info), where
      `segments` is a LAZY GENERATOR (transcription only runs as you
      iterate it) and each segment has .start/.end/.text in seconds.
"""

from __future__ import annotations

import logging
import threading

from . import config

logger = logging.getLogger("kajian_whisper")

# ISO-639-1 codes faster-whisper's tokenizer documents support for. Not
# enforced strictly, just used to normalize common BCP-47 locale ids the
# app sends (e.g. "id_ID" -> "id"). Both "id" (Indonesian) and "ar"
# (Arabic) are confirmed present in faster_whisper's own language list.
SUPPORTED_LANGUAGES = {
    "en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr", "pl", "ca",
    "nl", "ar", "sv", "it", "id", "hi", "fi", "vi", "he", "uk", "el", "ms",
    "cs", "ro", "da", "hu", "ta", "no", "th", "ur", "hr", "bg", "lt", "la",
    "mi", "ml", "cy", "sk", "te", "fa", "lv", "bn", "sr", "az", "sl", "kn",
    "et", "mk", "br", "eu", "is", "hy", "ne", "mn", "bs", "kk", "sq", "sw",
    "gl", "mr", "pa", "si", "km", "sn", "yo", "so", "af", "oc", "ka", "be",
    "tg", "sd", "gu", "am", "yi", "lo", "uz", "fo", "ht", "ps", "tk", "nn",
    "mt", "sa", "lb", "my", "bo", "tl", "mg", "as", "tt", "haw", "ln", "ha",
    "ba", "jw", "su",
}


class WhisperModelWrapper:
    """Thread-safe wrapper around a single loaded faster-whisper instance.

    A lock serializes calls into the model. CTranslate2 can run multiple
    concurrent transcriptions with `num_workers` > 1, but that increases
    VRAM/CPU-thread use — a homelab box serving one app's traffic doesn't
    need that complexity, so this keeps num_workers at faster-whisper's
    default (1) and serializes instead.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model = None

    def load(self) -> None:
        if self._model is not None:
            return
        logger.info(
            "Loading Whisper %s via faster-whisper (device=%s, compute_type=%s) ...",
            config.MODEL_SIZE, config.DEVICE, config.COMPUTE_TYPE,
        )
        # Imported lazily so config-only tooling doesn't need
        # faster_whisper/ctranslate2 installed (e.g. this module is
        # imported by tests that mock it out).
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]

        self._model = WhisperModel(
            config.MODEL_SIZE,
            device=config.DEVICE,
            compute_type=config.COMPUTE_TYPE,
            download_root=config.MODEL_CACHE_DIR,
        )
        logger.info("Model loaded.")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> str:
        return config.DEVICE

    def normalize_language(self, locale_id: str | None) -> str | None:
        """Maps a BCP-47 locale (e.g. "id_ID") to the bare language code
        faster-whisper expects (e.g. "id"). Returns None (auto-detect) if
        the locale is missing or unrecognized."""
        if not locale_id:
            return None
        code = locale_id.split("_")[0].split("-")[0].lower()
        return code if code in SUPPORTED_LANGUAGES else None

    def transcribe(self, audio_path: str, locale_id: str | None) -> list[dict]:
        """Transcribes an entire audio file in one call — faster-whisper
        handles long-form audio internally, no manual chunking needed.

        Returns a list of {"id", "text", "startMs", "endMs", "isFinal"}
        dicts, matching the app's /transcribe contract directly (see
        docs/BACKEND.md in the Flutter repo).
        """
        if self._model is None:
            raise RuntimeError("WhisperModelWrapper.load() must be called before use")

        language = self.normalize_language(locale_id)

        with self._lock:
            # `segments` is a generator — iterate it while still holding
            # the lock, since that's when the actual model inference runs.
            segments, _info = self._model.transcribe(
                audio_path,
                language=language,
                vad_filter=True,  # skip long silences common in lecture recordings
            )
            results = [
                {
                    "id": str(i),
                    "text": seg.text.strip(),
                    "startMs": round(seg.start * 1000),
                    "endMs": round(seg.end * 1000),
                    "isFinal": True,
                }
                for i, seg in enumerate(segments)
                if seg.text.strip()
            ]

        return results


# Module-level singleton, initialized at FastAPI startup (see main.py).
model = WhisperModelWrapper()
