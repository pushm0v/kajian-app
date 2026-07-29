"""Audio decoding for speaker embedding extraction.

sherpa-onnx's SpeakerEmbeddingExtractor needs a raw waveform handed to it
directly, so uploads are decoded here via ffmpeg before extraction. Ported
as-is from ../backend-whisper/app/audio.py (which in turn came from
../backend/) rather than shared/vendored, since these are independently
deployable containers with no common package.
"""

from __future__ import annotations

import subprocess

import numpy as np

from . import config


class AudioDecodeError(RuntimeError):
    pass


def decode_to_mono_16k(input_path: str) -> np.ndarray:
    """Decodes any ffmpeg-readable audio file to a float32 mono waveform at
    config.TARGET_SAMPLE_RATE, entirely in memory (stdout pipe, no temp wav).
    """
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-loglevel", "error",
        "-i", input_path,
        "-f", "f32le",
        "-ac", "1",
        "-ar", str(config.TARGET_SAMPLE_RATE),
        "pipe:1",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, check=True)
    except FileNotFoundError as e:
        raise AudioDecodeError(
            "ffmpeg is not installed or not on PATH in this container/host"
        ) from e
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        raise AudioDecodeError(f"ffmpeg failed to decode audio: {stderr}") from e

    return np.frombuffer(proc.stdout, dtype=np.float32)
