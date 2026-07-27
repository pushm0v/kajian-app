"""Proxies transcription requests to the actual ASR inference workers
(../backend/ for Qwen3-ASR, ../backend-whisper/ for Whisper large-v3).

Those two services stay deliberately dumb/stateless — pure inference, no
auth, no database, no knowledge of users or sessions — so they can be
scaled, restarted, or redeployed independently of everything else. This
module is the only thing in backend-core that talks to them directly.
"""

from __future__ import annotations

import enum
import logging
import os
import time

import httpx

from .. import config

logger = logging.getLogger("kajian_core")


class AsrModel(str, enum.Enum):
    qwen = "qwen"
    whisper = "whisper"


class AsrModelUnavailable(RuntimeError):
    pass


def _worker_config(model: AsrModel) -> tuple[str, str]:
    if model == AsrModel.qwen:
        return config.QWEN_BACKEND_URL, config.QWEN_BACKEND_TOKEN
    return config.WHISPER_BACKEND_URL, config.WHISPER_BACKEND_TOKEN


async def transcribe(model: AsrModel, audio_path: str, locale_id: str) -> dict:
    """Sends `audio_path` to the chosen ASR worker's POST /transcribe and
    returns its JSON response verbatim (segments + benchmarking metadata —
    see docs/BACKEND.md in the Flutter repo for the exact shape)."""
    base_url, token = _worker_config(model)
    if not base_url:
        logger.warning("No ASR backend configured for model=%s", model.value)
        raise AsrModelUnavailable(f"No backend configured for model={model.value}")

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    audio_bytes = os.path.getsize(audio_path)
    logger.info(
        "ASR proxy: POST %s/transcribe (model=%s, locale=%s, audio_bytes=%d) ...",
        base_url, model.value, locale_id, audio_bytes,
    )
    started = time.monotonic()

    try:
        # No timeout: batch transcription of a long recording can
        # legitimately take minutes on this hardware — a finite timeout
        # would abort in-progress requests, not just hung ones. Progress is
        # only visible via these logs (before/after), not a request
        # deadline.
        async with httpx.AsyncClient(timeout=None) as client:
            with open(audio_path, "rb") as f:
                response = await client.post(
                    f"{base_url}/transcribe",
                    headers=headers,
                    data={"locale": locale_id, "model": model.value},
                    files={"audio": (audio_path.rsplit("/", 1)[-1], f, "audio/m4a")},
                )
        response.raise_for_status()
    except Exception:
        logger.exception(
            "ASR proxy failed after %.1fs (model=%s, %s/transcribe)",
            time.monotonic() - started, model.value, base_url,
        )
        raise

    elapsed = time.monotonic() - started
    result = response.json()
    logger.info(
        "ASR proxy: %s/transcribe completed in %.1fs, %d segment(s)",
        base_url, elapsed, len(result.get("segments", [])),
    )
    return result
