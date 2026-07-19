"""Unit tests for the chunking logic — no model/ffmpeg required."""

import numpy as np

from app.audio import chunk_waveform


def test_chunk_waveform_tiles_exactly_with_no_gaps():
    sample_rate = 16_000
    duration_s = 95.0
    samples = np.zeros(int(duration_s * sample_rate), dtype=np.float32)

    chunks = chunk_waveform(
        samples, sample_rate, chunk_seconds=30.0, overlap_seconds=1.0,
    )

    # 95s / 30s -> 4 chunks: [0,30) [30,60) [60,90) [90,95)
    assert [round(s, 3) for _, s, _ in chunks] == [0.0, 30.0, 60.0, 90.0]
    assert [round(e, 3) for _, _, e in chunks] == [30.0, 60.0, 90.0, 95.0]

    # Core spans must be contiguous with no gap or overlap in the reported
    # timestamps (only the audio handed to the model overlaps, not the
    # timestamps attributed to each chunk).
    for i in range(len(chunks) - 1):
        assert chunks[i][2] == chunks[i + 1][1]


def test_chunk_waveform_includes_overlap_padding_in_audio():
    sample_rate = 16_000
    samples = np.zeros(int(65 * sample_rate), dtype=np.float32)

    chunks = chunk_waveform(
        samples, sample_rate, chunk_seconds=30.0, overlap_seconds=1.0,
    )

    # Middle chunk [30,60) should include 1s padding on both sides -> 32s of
    # audio samples, even though its reported span is exactly 30s.
    middle_audio, start, end = chunks[1]
    assert end - start == 30.0
    assert len(middle_audio) == int(32 * sample_rate)


def test_chunk_waveform_empty_audio_returns_no_chunks():
    samples = np.zeros(0, dtype=np.float32)
    chunks = chunk_waveform(samples, 16_000, chunk_seconds=30.0, overlap_seconds=1.0)
    assert chunks == []


def test_chunk_waveform_short_audio_single_chunk():
    sample_rate = 16_000
    samples = np.zeros(int(5 * sample_rate), dtype=np.float32)
    chunks = chunk_waveform(samples, sample_rate, chunk_seconds=30.0, overlap_seconds=1.0)
    assert len(chunks) == 1
    _, start, end = chunks[0]
    assert (start, end) == (0.0, 5.0)
