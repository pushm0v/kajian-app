"""Speaker embedding extraction via sherpa-onnx's CAM++ model — a small
(192-dim) voice fingerprint used to suggest matching speakers across
sessions. See config.py's SPEAKER_EMBEDDING_MODEL_PATH comment for why
this model.

Lives in this container (not the Qwen worker's, where this originally
shipped) because this container's CUDA 12/cuDNN 9 base image matches what
sherpa-onnx's GPU wheel targets, unlike the Qwen worker's CUDA 13.2/torch
2.10 stack (a real risk of two independently-bundled CUDA runtimes
conflicting in one process). GPU provider is opt-in, not default: in
practice Whisper large-v3 at float16 was found to already consume nearly
this whole 12GB card (~11.6GB), leaving too little headroom for
sherpa-onnx's CUDA execution provider (a 27MB model still needed ~2.75GB
for a single Conv node's workspace — a known ONNX Runtime CUDA EP
over-allocation pattern, not a bug specific to this model). CPU defaults
until that's tuned (arena/allocator settings, or a smaller Whisper
compute_type) and confirmed to actually fit.

Supports switching provider at runtime (see load()) — reloads the
extractor on demand rather than keeping both a CPU and GPU instance
loaded simultaneously, since the GPU one may simply fail to load/run
depending on current VRAM pressure from Whisper.

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

logger = logging.getLogger("kajian_whisper")


class SpeakerEmbedder:
    """Thread-safe wrapper around a single loaded sherpa-onnx speaker
    embedding extractor. Mirrors WhisperModelWrapper's load()/lock/
    singleton shape (see asr_model.py), but additionally supports
    reloading with a different provider on demand (see load())."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._extractor = None
        self._provider: str | None = None

    def load(self, provider: str | None = None) -> None:
        """Loads the extractor with `provider` ("cpu" or "cuda"), or
        config.SPEAKER_EMBEDDING_PROVIDER if not given. A no-op if already
        loaded with that same provider; reloads (replacing the extractor)
        if a different provider is requested — e.g. the dev-console's
        provider toggle, see main.py's /embed-speaker.
        """
        provider = provider or config.SPEAKER_EMBEDDING_PROVIDER
        if self._extractor is not None and self._provider == provider:
            return

        logger.info(
            "Loading speaker embedding model from %s (provider=%s, num_threads=%d) ...",
            config.SPEAKER_EMBEDDING_MODEL_PATH, provider, config.SPEAKER_EMBEDDING_NUM_THREADS,
        )
        # Imported lazily so config-only tooling doesn't need sherpa_onnx
        # installed (matches asr_model.py's lazy faster_whisper import).
        import sherpa_onnx  # noqa: PLC0415

        embedder_config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=config.SPEAKER_EMBEDDING_MODEL_PATH,
            num_threads=config.SPEAKER_EMBEDDING_NUM_THREADS,
            provider=provider,
        )
        if not embedder_config.validate():
            raise RuntimeError(
                f"Invalid speaker embedding config: {embedder_config} "
                f"(check SPEAKER_EMBEDDING_MODEL_PATH exists and the sherpa-onnx "
                f"GPU wheel is installed if provider=cuda)"
            )
        with self._lock:
            self._extractor = sherpa_onnx.SpeakerEmbeddingExtractor(embedder_config)
            self._provider = provider
        logger.info(
            "Speaker embedding model loaded (dim=%d, provider=%s).",
            self._extractor.dim, provider,
        )

    @property
    def is_loaded(self) -> bool:
        return self._extractor is not None

    @property
    def provider(self) -> str | None:
        return self._provider

    @property
    def dim(self) -> int:
        if self._extractor is None:
            raise RuntimeError("SpeakerEmbedder.load() must be called before use")
        return self._extractor.dim

    def embed(self, waveform: np.ndarray, sample_rate: int, provider: str | None = None) -> list[float]:
        """Extracts a speaker embedding from a mono float32 waveform.

        `waveform` should be the same 16kHz mono float32 array
        decode_to_mono_16k already produces — no separate decode needed.
        If `provider` differs from what's currently loaded, reloads the
        extractor first (see load()) — a few seconds of one-time cost
        when switching, not a per-call cost otherwise.
        Returns a plain list[float] (JSON-serializable) rather than an
        ndarray, since this crosses an HTTP boundary (see main.py).
        """
        self.load(provider)

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
