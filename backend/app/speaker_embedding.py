"""Speaker embedding extraction via sherpa-onnx's CAM++ model — a small
(192-dim), CPU-only voice fingerprint used to suggest matching speakers
across sessions. See config.py's SPEAKER_EMBEDDING_MODEL_PATH comment for
why this model and why CPU-only.

Deliberately separate from asr_model.py: different runtime (ONNX Runtime,
not vLLM/PyTorch), different device (CPU, not GPU), different lifecycle
(stateless per-call, no KV cache/lock contention with ASR inference).

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

logger = logging.getLogger("kajian_asr")


class SpeakerEmbedder:
    """Thread-safe wrapper around a single loaded sherpa-onnx speaker
    embedding extractor. Mirrors AsrModel's load()/lock/singleton shape."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._extractor = None

    def load(self) -> None:
        if self._extractor is not None:
            return
        logger.info(
            "Loading speaker embedding model from %s ...",
            config.SPEAKER_EMBEDDING_MODEL_PATH,
        )
        # Imported lazily so config-only tooling doesn't need sherpa_onnx
        # installed (matches asr_model.py's lazy vllm/transformers imports).
        import sherpa_onnx  # noqa: PLC0415

        embedder_config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=config.SPEAKER_EMBEDDING_MODEL_PATH,
            num_threads=1,
            provider="cpu",
        )
        if not embedder_config.validate():
            raise RuntimeError(
                f"Invalid speaker embedding config: {embedder_config} "
                f"(check SPEAKER_EMBEDDING_MODEL_PATH exists)"
            )
        self._extractor = sherpa_onnx.SpeakerEmbeddingExtractor(embedder_config)
        logger.info(
            "Speaker embedding model loaded (dim=%d).", self._extractor.dim,
        )

    @property
    def is_loaded(self) -> bool:
        return self._extractor is not None

    @property
    def dim(self) -> int:
        if self._extractor is None:
            raise RuntimeError("SpeakerEmbedder.load() must be called before use")
        return self._extractor.dim

    def embed(self, waveform: np.ndarray, sample_rate: int) -> list[float]:
        """Extracts a speaker embedding from a mono float32 waveform.

        `waveform` should be the same 16kHz mono float32 array
        decode_to_mono_16k already produces — no separate decode needed.
        Returns a plain list[float] (JSON-serializable) rather than an
        ndarray, since this crosses an HTTP boundary (see main.py).
        """
        if self._extractor is None:
            raise RuntimeError("SpeakerEmbedder.load() must be called before use")

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
