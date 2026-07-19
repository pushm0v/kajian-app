"""Loads Qwen3-ASR-1.7B once at startup and exposes a simple transcribe(...)
call for a single chunk of audio.

Uses the official `qwen_asr` package (`pip install qwen-asr`), which wraps
Hugging Face `transformers` and handles resampling / feature extraction
internally. See https://huggingface.co/Qwen/Qwen3-ASR-1.7B for model details.

Qwen3-ASR outputs plain text only (no timestamps) — this module is
intentionally single-purpose: text in, text out for one bounded audio clip.
Chunking a long recording into multiple calls and assigning timestamps from
chunk boundaries is handled by the caller (see transcription.py).
"""

from __future__ import annotations

import logging
import threading

import numpy as np
import torch

from . import config

logger = logging.getLogger("kajian_asr")

# ISO-639-1 codes Qwen3-ASR officially documents support for. Not enforced
# strictly (the model may do reasonably on others), just used to normalize
# common BCP-47 locale ids the app sends (e.g. "id_ID" -> "id").
SUPPORTED_LANGUAGES = {
    "zh", "yue", "en", "ar", "de", "fr", "es", "pt", "id", "it", "ko", "ru",
    "th", "vi", "ja", "tr", "hi", "ms", "nl", "sv", "da", "fi", "pl", "cs",
    "fil", "fa", "el", "hu", "mk", "ro",
}


def _resolve_device() -> str:
    if config.DEVICE != "auto":
        return config.DEVICE
    return "cuda" if torch.cuda.is_available() else "cpu"


def _resolve_dtype(device: str) -> torch.dtype:
    if device == "cpu":
        # bf16/fp16 matmul on CPU is either unsupported or very slow on most
        # hardware; fall back to fp32 regardless of the configured dtype.
        return torch.float32
    return {
        "bfloat16": torch.bfloat16,
        "float16": torch.float16,
        "float32": torch.float32,
    }[config.TORCH_DTYPE]


class AsrModel:
    """Thread-safe wrapper around a single loaded Qwen3-ASR model instance.

    Model inference isn't safely reentrant across threads for a single model
    object in all backends, so a lock serializes calls. This is fine for a
    homelab single-GPU box serving one app's worth of traffic.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model = None
        self.device = _resolve_device()
        self.dtype = _resolve_dtype(self.device)

    def load(self) -> None:
        if self._model is not None:
            return
        logger.info(
            "Loading %s on device=%s dtype=%s ...",
            config.MODEL_ID, self.device, self.dtype,
        )
        # Imported lazily so `config.py`-only tooling (e.g. tests that don't
        # need the model) doesn't require qwen_asr/torch to be installed.
        from qwen_asr import Qwen3ASR  # type: ignore[import-not-found]

        self._model = Qwen3ASR(
            model=config.MODEL_ID,
            device=self.device,
            dtype=self.dtype,
        )
        logger.info("Model loaded.")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def normalize_language(self, locale_id: str | None) -> str | None:
        """Maps a BCP-47 locale (e.g. "id_ID") to the bare language code
        Qwen3-ASR expects (e.g. "id"). Returns None (auto-detect) if the
        locale is missing or unrecognized."""
        if not locale_id:
            return None
        code = locale_id.split("_")[0].split("-")[0].lower()
        return code if code in SUPPORTED_LANGUAGES else None

    def transcribe_chunk(
        self,
        audio: np.ndarray,
        sample_rate: int,
        language: str | None,
    ) -> str:
        """Transcribes a single bounded audio clip (< ~20 minutes, per the
        model's documented limit — callers should chunk well below that).

        Returns the transcribed text, stripped. Empty string for silence.
        """
        if self._model is None:
            raise RuntimeError("AsrModel.load() must be called before use")

        with self._lock:
            result = self._model.transcribe(
                (audio, sample_rate),
                language=language,
            )
        text = getattr(result, "text", None) or getattr(result, "transcript", "")
        return str(text).strip()


# Module-level singleton, initialized at FastAPI startup (see main.py).
model = AsrModel()
