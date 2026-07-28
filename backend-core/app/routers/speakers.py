"""GET /speakers (the confirmed voice-fingerprint library) and
POST /sessions/{id}/speaker-confirm (the only route allowed to write
KajianSession.speaker_id — see services/speaker_matching.py's docstring
on why nothing else in this codebase does).

Speaker profiles are global (shared across all users of this self-hosted
instance, not scoped per-user) — the same ustadz recorded by different
users should resolve to the same profile. See sessions.py for the
per-user-scoped session routes this file deliberately doesn't mirror.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas
from ..auth import current_user
from ..db import get_db
from ..models.speaker import Speaker
from ..models.user import User
from ..services.speaker_matching import find_best_match, update_centroid
from .sessions import _get_owned_session, _to_out

logger = logging.getLogger("kajian_core")

router = APIRouter(tags=["speakers"])


@router.get("/speakers", response_model=list[schemas.SpeakerOut])
async def list_speakers(
    _user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    # Auth-gated (any signed-in user can list) but not user-scoped — the
    # library is global, see this module's docstring.
    result = await db.execute(select(Speaker).order_by(Speaker.name))
    return list(result.scalars().all())


@router.get(
    "/sessions/{session_id}/speaker-suggestion",
    response_model=schemas.SuggestedSpeakerOut | None,
)
async def get_speaker_suggestion(
    session_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recomputes and returns the current best speaker match for
    session.pending_embedding, or null if there's no pending embedding or
    no candidate clears the threshold.

    transcribe_session (routers/processing.py) now runs in the
    background — there's no request/response left to attach a suggestion
    to by the time embedding extraction finishes, so the client polls
    GET /sessions/{id} for job completion, then calls this separately to
    fetch (or re-fetch) the suggestion. Cheap to recompute on every call
    (cosine similarity against a handful of stored speakers, no
    re-embedding), so it's always current even if the speaker library
    changed since transcription finished.
    """
    session = await _get_owned_session(db, user, session_id)
    if session.pending_embedding is None:
        return None

    result = await db.execute(select(Speaker))
    candidates = list(result.scalars().all())
    match = find_best_match(session.pending_embedding, candidates)
    if match is None:
        return None

    speaker, score = match
    return schemas.SuggestedSpeakerOut(speakerId=str(speaker.id), name=speaker.name, score=round(score, 3))


@router.post("/sessions/{session_id}/speaker-confirm", response_model=schemas.KajianSessionOut)
async def confirm_speaker(
    session_id: str,
    body: schemas.SpeakerConfirmIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirms a suggested speaker match (speakerId) or enrolls this
    session's embedding under a brand-new profile (newSpeakerName). This
    is the ONLY place KajianSession.speaker_id is ever written — an
    embedding match alone (see routers/processing.py's transcribe_session)
    only ever surfaces a suggestion, never assigns.
    """
    session = await _get_owned_session(db, user, session_id)
    if session.audio_object_key is None:
        raise HTTPException(status_code=400, detail="Session has no uploaded audio")

    embedding = session.pending_embedding
    if embedding is None:
        raise HTTPException(
            status_code=400,
            detail="No pending speaker embedding for this session — run /transcribe first",
        )

    if body.speakerId and body.newSpeakerName:
        raise HTTPException(status_code=422, detail="Provide speakerId OR newSpeakerName, not both")

    if body.speakerId:
        result = await db.execute(select(Speaker).where(Speaker.id == body.speakerId))
        speaker = result.scalar_one_or_none()
        if speaker is None:
            raise HTTPException(status_code=404, detail="Speaker not found")
        update_centroid(speaker, embedding)
        logger.info(
            "speaker-confirm: session=%s confirmed existing speaker=%s (embedding_count=%d)",
            session_id, speaker.id, speaker.embedding_count,
        )
    elif body.newSpeakerName:
        speaker = Speaker(name=body.newSpeakerName, embedding=embedding, embedding_count=1)
        db.add(speaker)
        await db.flush()  # assign speaker.id before we reference it below
        logger.info(
            "speaker-confirm: session=%s enrolled new speaker=%s name=%r",
            session_id, speaker.id, body.newSpeakerName,
        )
    else:
        raise HTTPException(status_code=422, detail="Provide either speakerId or newSpeakerName")

    session.speaker_id = speaker.id
    session.pending_embedding = None
    if not session.speaker:
        session.speaker = speaker.name
    await db.commit()

    return _to_out(await _get_owned_session(db, user, session_id))
