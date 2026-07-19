"""Audio decoding and chunking.

The app records .m4a (AAC). We shell out to ffmpeg to decode+resample to
16kHz mono PCM once, then slice that in-memory waveform into fixed-size
overlapping chunks for the ASR model.
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


def chunk_waveform(
    samples: np.ndarray,
    sample_rate: int,
    chunk_seconds: float,
    overlap_seconds: float,
) -> list[tuple[np.ndarray, float, float]]:
    """Splits `samples` into overlapping chunks.

    Returns a list of (chunk_samples, start_seconds, end_seconds), where
    start/end describe the *core* (non-overlapping) span each chunk is
    responsible for — the actual audio handed to the model includes a bit
    of look-ahead/look-behind context from `overlap_seconds` on each side to
    reduce words getting cut at a chunk boundary, but the reported timestamp
    span stays at the core boundaries so segments tile the recording exactly
    with no gaps or double-counted time.
    """
    total_samples = len(samples)
    total_seconds = total_samples / sample_rate
    core = chunk_seconds
    pad = overlap_seconds

    chunks: list[tuple[np.ndarray, float, float]] = []
    start = 0.0
    while start < total_seconds:
        end = min(start + core, total_seconds)

        pad_start = max(0.0, start - pad)
        pad_end = min(total_seconds, end + pad)

        i0 = int(pad_start * sample_rate)
        i1 = int(pad_end * sample_rate)
        chunk = samples[i0:i1]

        if chunk.size > 0:
            chunks.append((chunk, start, end))

        start = end

    return chunks
