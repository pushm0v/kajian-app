"""Matches a new speaker embedding against the stored voice-fingerprint
library via cosine similarity — plain NumPy, no vector DB (dozens/hundreds
of speakers doesn't justify one; see the design discussion this module
came out of).

Cosine similarity, not raw dot product: sherpa-onnx's own
SpeakerEmbeddingExtractor.compute() returns a RAW, un-normalized
embedding (confirmed against its C++ source — normalization is NOT baked
into the extractor). dot(a,b)/(norm(a)*norm(b)) is equivalent to
L2-normalizing both vectors first and taking the dot product, without
needing to pre-normalize anything stored — so it's safe to apply directly
to the raw embeddings coming back from backend/'s /embed-speaker.

Suggestions only — nothing in this module ever assigns a speaker_id
itself. See routers/processing.py for how a suggestion is surfaced, and
routers/speakers.py for the explicit user-confirmation endpoint that's
the only thing allowed to write speaker_id.
"""

from __future__ import annotations

import numpy as np

from .. import config
from ..models.speaker import Speaker


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0.0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def find_best_match(
    embedding: list[float], candidates: list[Speaker],
) -> tuple[Speaker, float] | None:
    """Returns (best-matching Speaker, score) if its score clears
    config.SPEAKER_MATCH_THRESHOLD, else None (below threshold = no
    suggestion — see this module's docstring on why nothing here
    auto-assigns)."""
    if not candidates:
        return None

    scored = [(speaker, cosine_similarity(embedding, speaker.embedding)) for speaker in candidates]
    best_speaker, best_score = max(scored, key=lambda pair: pair[1])
    if best_score < config.SPEAKER_MATCH_THRESHOLD:
        return None
    return best_speaker, best_score


def update_centroid(speaker: Speaker, new_embedding: list[float]) -> None:
    """Incrementally averages `new_embedding` into `speaker.embedding`,
    weighted by how many prior enrollments contributed — so one noisy
    recording can't outweigh a well-established profile, and repeated
    confirmations for the same person converge toward a stable centroid
    rather than drifting toward whichever recording was enrolled last."""
    old = np.asarray(speaker.embedding, dtype=np.float64)
    new = np.asarray(new_embedding, dtype=np.float64)
    n = speaker.embedding_count
    centroid = (old * n + new) / (n + 1)
    speaker.embedding = centroid.astype(np.float32).tolist()
    speaker.embedding_count = n + 1
