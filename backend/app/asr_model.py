"""Loads Qwen3-ASR-1.7B once at startup via the qwen_asr package's vLLM
backend, and exposes both a batch transcribe(...) call (for the existing
/transcribe endpoint) and a streaming session API (for /transcribe/stream).

Consolidated onto vLLM (rather than transformers) because real streaming
transcription is only available on the vLLM backend — see
https://github.com/QwenLM/Qwen3-ASR. Running both backends loaded at once
isn't attempted here; a single 6GB+ GPU comfortably fits one.

API surface used (qwen_asr.Qwen3ASRModel, confirmed against the package
source — qwen_asr/inference/qwen3_asr.py):
  - Qwen3ASRModel.LLM(model=..., **vllm_kwargs) -> loads via vllm.LLM(...)
  - .transcribe(audio=(np.ndarray, sr), language=...) -> batch/offline
  - .init_streaming_state(unfixed_chunk_num, unfixed_token_num,
      chunk_size_sec) -> a mutable per-session state object
  - .streaming_transcribe(pcm16k, state) -> updates state.text in place
      (cumulative full transcript so far, not a delta)
  - .finish_streaming_transcribe(state) -> flushes the tail buffer and
      returns the same state, one last time
"""

from __future__ import annotations

import logging
import threading

import numpy as np

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


class AsrModel:
    """Thread-safe wrapper around a single loaded Qwen3-ASR vLLM instance.

    A lock serializes calls into the model. vLLM batches internally, but
    qwen_asr's Python wrapper isn't documented as safe for concurrent calls
    from multiple threads on one instance, and a homelab box serving one
    app's traffic doesn't need that complexity.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model = None

    def load(self) -> None:
        if self._model is not None:
            return
        logger.info(
            "Loading %s via vLLM (gpu_memory_utilization=%.2f) ...",
            config.MODEL_ID, config.GPU_MEMORY_UTILIZATION,
        )
        # Imported lazily so config-only tooling doesn't need qwen_asr/vllm
        # installed (e.g. this module is imported by tests that mock it out).
        from qwen_asr import Qwen3ASRModel  # type: ignore[import-not-found]

        self._model = Qwen3ASRModel.LLM(
            model=config.MODEL_ID,
            gpu_memory_utilization=config.GPU_MEMORY_UTILIZATION,
        )
        logger.info("Model loaded.")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> str:
        # vLLM always targets CUDA for this model; kept as a property (not a
        # hardcoded string in main.py) so /health stays a single source of
        # truth if that ever changes.
        return "cuda"

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
            [result] = self._model.transcribe(
                audio=(audio, sample_rate),
                language=language,
            )
        return str(result.text).strip()

    def new_streaming_state(self):
        """Starts a new incremental-decoding session for one live connection.

        Returned state is only safe to use from a single caller at a time —
        each WebSocket connection gets its own via this method.
        """
        if self._model is None:
            raise RuntimeError("AsrModel.load() must be called before use")
        with self._lock:
            return self._model.init_streaming_state(
                unfixed_chunk_num=config.STREAM_UNFIXED_CHUNK_NUM,
                unfixed_token_num=config.STREAM_UNFIXED_TOKEN_NUM,
                chunk_size_sec=config.STREAM_CHUNK_SIZE_SEC,
            )

    def streaming_transcribe(self, pcm16k: np.ndarray, state) -> str:
        """Feeds another slice of 16kHz mono audio into `state`.

        Returns the *cumulative* transcript so far (state.text), not just
        the new text since the last call — the caller is responsible for
        diffing against what it already sent the client, if needed.
        """
        with self._lock:
            self._model.streaming_transcribe(pcm16k, state)
        return str(state.text).strip()

    def finish_streaming(self, state) -> str:
        """Flushes any buffered tail audio and returns the final cumulative
        transcript for this session. Call once when the client stops
        streaming (end of recording, or the connection closes)."""
        with self._lock:
            self._model.finish_streaming_transcribe(state)
        return str(state.text).strip()


# Module-level singleton, initialized at FastAPI startup (see main.py).
model = AsrModel()
