"""Orchestrates decode -> chunk -> transcribe -> segment list.

Produces output matching the app's /transcribe contract (see
docs/BACKEND.md in the Flutter repo):

    {"segments": [{"id": "0", "text": "...", "startMs": 0, "endMs": 30000,
                    "isFinal": true}, ...]}

Timestamps are chunk-boundary approximations, not word-level alignment —
see the design note in asr_model.py for why (Qwen3-ASR has no built-in
timestamps, and the official forced-aligner model doesn't cover
Indonesian/Arabic, this app's primary languages).
"""

from __future__ import annotations

import logging

from . import config
from .asr_model import AsrModel
from .audio import chunk_waveform, decode_to_mono_16k

logger = logging.getLogger("kajian_asr")


def transcribe_file(model: AsrModel, audio_path: str, locale_id: str | None) -> list[dict]:
    samples = decode_to_mono_16k(audio_path)
    if samples.size == 0:
        return []

    language = model.normalize_language(locale_id)
    chunks = chunk_waveform(
        samples,
        sample_rate=config.TARGET_SAMPLE_RATE,
        chunk_seconds=config.CHUNK_SECONDS,
        overlap_seconds=config.CHUNK_OVERLAP_SECONDS,
    )
    logger.info(
        "Transcribing %d chunk(s), language=%s, total=%.1fs",
        len(chunks), language or "auto", samples.size / config.TARGET_SAMPLE_RATE,
    )

    segments: list[dict] = []
    for i, (chunk_audio, start_s, end_s) in enumerate(chunks):
        text = model.transcribe_chunk(
            chunk_audio,
            sample_rate=config.TARGET_SAMPLE_RATE,
            language=language,
        )
        if not text:
            continue
        segments.append({
            "id": str(i),
            "text": text,
            "startMs": round(start_s * 1000),
            "endMs": round(end_s * 1000),
            "isFinal": True,
        })

    return segments
