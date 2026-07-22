"""Proxies transcription requests to the actual ASR inference workers
(../backend/ for Qwen3-ASR, ../backend-whisper/ for Whisper large-v3).

Those two services stay deliberately dumb/stateless — pure inference, no
auth, no database, no knowledge of users or sessions — so they can be
scaled, restarted, or redeployed independently of everything else. This
module is the only thing in backend-core that talks to them directly.
"""

from __future__ import annotations

import enum

import httpx

from .. import config


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
        raise AsrModelUnavailable(f"No backend configured for model={model.value}")

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    async with httpx.AsyncClient(timeout=None) as client:
        with open(audio_path, "rb") as f:
            response = await client.post(
                f"{base_url}/transcribe",
                headers=headers,
                data={"locale": locale_id, "model": model.value},
                files={"audio": (audio_path.rsplit("/", 1)[-1], f, "audio/m4a")},
            )
    response.raise_for_status()
    return response.json()
