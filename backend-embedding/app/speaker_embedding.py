"""Speaker embedding extraction via sherpa-onnx — a small (192-dim) voice
fingerprint used to suggest matching speakers across sessions.

This is the whole job of this container. It previously rode along inside
../backend-whisper/, which forced an awkward compromise: that GPU is
almost entirely consumed by Whisper large-v3's weights, so the embedding
step had to default to CPU (~93s for a 44-minute recording) even though
the model itself is tiny. Splitting it out onto its own card removes that
constraint — see config.py's PROVIDER comment for the measured numbers.

Model choice is configurable (config.MODELS) rather than hardcoded,
because the accuracy question here is genuinely open: the default CAM++
checkpoint is the only *multilingual* option available, but ERes2NetV2 is
a stronger architecture that happens to be Chinese-only. Which one
transfers better to Indonesian kajian audio is an empirical question, so
both are baked in and switchable.

API confirmed against sherpa-onnx 1.13.4's own python-api-examples/
speaker-identification.py and speaker-embedding-manager.cc:
  - SpeakerEmbeddingExtractorConfig(model=..., num_threads=..., provider=...)
  - extractor.create_stream() -> stream.accept_waveform(sample_rate, samples)
    -> stream.input_finished() -> extractor.compute(stream)
  - compute() returns a RAW, un-normalized embedding — sherpa-onnx's own
    SpeakerEmbeddingManager L2-normalizes internally before comparing.
    Cosine similarity (dot(a,b)/(norm(a)*norm(b))) is used at the
    comparison layer instead (see backend-core's speaker_matching.py),
    which is equivalent without needing to pre-normalize here.
"""

from __future__ import annotations

import logging
import threading

import numpy as np

from . import config

logger = logging.getLogger("kajian_embedding")


class SpeakerEmbedder:
    """Thread-safe wrapper around a single loaded sherpa-onnx speaker
    embedding extractor, supporting reload with a different provider or
    model on demand (see load())."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._extractor = None
        self._provider: str | None = None
        self._model_path: str | None = None

    def load(self, provider: str | None = None, model_path: str | None = None) -> None:
        """Loads the extractor with `provider` ("cpu"/"cuda") and
        `model_path`, defaulting to config.PROVIDER/config.MODEL_PATH.

        A no-op if already loaded with that same pair; otherwise replaces
        the extractor. Only one is held at a time rather than caching an
        instance per provider — the GPU one may simply fail to load
        depending on current VRAM pressure, and keeping a stale CPU copy
        alive to hedge that costs memory for a step that runs once per
        transcription.
        """
        provider = provider or config.PROVIDER
        model_path = model_path or config.MODEL_PATH
        if (
            self._extractor is not None
            and self._provider == provider
            and self._model_path == model_path
        ):
            return

        logger.info(
            "Loading speaker embedding model from %s (provider=%s, num_threads=%d) ...",
            model_path, provider, config.NUM_THREADS,
        )
        # Imported lazily so config-only tooling (and the test suite) doesn't
        # need sherpa_onnx installed.
        import sherpa_onnx  # noqa: PLC0415

        embedder_config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=model_path,
            num_threads=config.NUM_THREADS,
            provider=provider,
        )
        if not embedder_config.validate():
            raise RuntimeError(
                f"Invalid speaker embedding config: {embedder_config} "
                f"(check the model file exists at {model_path} and that the "
                f"sherpa-onnx GPU wheel is installed if provider=cuda)"
            )
        with self._lock:
            self._extractor = sherpa_onnx.SpeakerEmbeddingExtractor(embedder_config)
            self._provider = provider
            self._model_path = model_path
        logger.info(
            "Speaker embedding model loaded (dim=%d, provider=%s, model=%s).",
            self._extractor.dim, provider, model_path,
        )

    @property
    def is_loaded(self) -> bool:
        return self._extractor is not None

    @property
    def provider(self) -> str | None:
        return self._provider

    @property
    def model_path(self) -> str | None:
        return self._model_path

    @property
    def dim(self) -> int:
        if self._extractor is None:
            raise RuntimeError("SpeakerEmbedder.load() must be called before use")
        return self._extractor.dim

    def embed(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        provider: str | None = None,
        model_path: str | None = None,
    ) -> list[float]:
        """Extracts a speaker embedding from a mono float32 waveform.

        `waveform` should be the same 16kHz mono float32 array
        decode_to_mono_16k already produces — no separate decode needed.
        If `provider`/`model_path` differ from what's currently loaded,
        reloads first (see load()) — a few seconds of one-time cost when
        switching, not a per-call cost otherwise.

        Returns a plain list[float] (JSON-serializable) rather than an
        ndarray, since this crosses an HTTP boundary (see main.py).
        """
        self.load(provider, model_path)

        with self._lock:
            stream = self._extractor.create_stream()
            stream.accept_waveform(
                sample_rate=sample_rate, waveform=waveform.astype(np.float32, copy=False),
            )
            stream.input_finished()
            if not self._extractor.is_ready(stream):
                raise RuntimeError("Speaker embedding stream not ready after input_finished()")
            embedding = self._extractor.compute(stream)
        return np.asarray(embedding, dtype=np.float32).tolist()


# Module-level singleton, initialized at FastAPI startup (see main.py).
embedder = SpeakerEmbedder()
