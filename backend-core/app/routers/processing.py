"""POST /sessions/{id}/transcribe and /summarize — orchestrates the
existing ASR workers (../backend/, ../backend-whisper/) and the Anthropic
notes service against a session's already-uploaded audio, persisting the
result directly rather than round-tripping it back to the app first.

This replaces the app's own SessionProvider.process() pipeline: the app
now asks the server to do the work and polls/reads back the updated
session, instead of calling CloudTranscriptionService/AiNotesService
directly and pushing the result up itself.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import config, schemas
from ..auth import current_user
from ..db import get_db
from ..models.kajian_note import KajianNote, ScriptureReference
from ..models.speaker import Speaker
from ..models.transcript_segment import TranscriptSegment
from ..models.user import User
from ..services import asr_proxy, notes, storage
from ..services.speaker_matching import find_best_match, update_centroid
from .sessions import _get_owned_session, _to_out

logger = logging.getLogger("kajian_core")

router = APIRouter(prefix="/sessions", tags=["processing"])


async def _match_speaker(
    db: AsyncSession, session, local_path: str,
) -> schemas.SuggestedSpeakerOut | None:
    """Extracts a speaker embedding for `session` and either auto-confirms
    it (exact, case-insensitive match against session.speaker's typed
    name) or stashes it as session.pending_embedding and returns a
    suggestion for the caller to surface — never both, never neither.
    Failures here are logged and swallowed: a speaker-embedding problem
    should never fail the transcription response it's riding along with.
    """
    try:
        embedding = await asr_proxy.embed_speaker(local_path)
    except Exception:  # noqa: BLE001 - best-effort; transcription already succeeded
        logger.exception("transcribe_session %s: speaker embedding failed, skipping", session.id)
        return None

    result = await db.execute(select(Speaker))
    candidates = list(result.scalars().all())

    if session.speaker:
        exact = next(
            (s for s in candidates if s.name.strip().lower() == session.speaker.strip().lower()),
            None,
        )
        if exact is not None:
            update_centroid(exact, embedding)
            session.speaker_id = exact.id
            logger.info(
                "transcribe_session %s: auto-confirmed exact-name match speaker=%s (embedding_count=%d)",
                session.id, exact.id, exact.embedding_count,
            )
            return None

    match = find_best_match(embedding, candidates)
    session.pending_embedding = embedding
    if match is None:
        logger.info("transcribe_session %s: no speaker match above threshold", session.id)
        return None

    speaker, score = match
    logger.info(
        "transcribe_session %s: suggesting speaker=%s (score=%.3f)", session.id, speaker.id, score,
    )
    return schemas.SuggestedSpeakerOut(speakerId=str(speaker.id), name=speaker.name, score=round(score, 3))


@router.post("/{session_id}/transcribe", response_model=schemas.KajianSessionOut)
async def transcribe_session(
    session_id: str,
    body: schemas.TranscribeRequestIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, user, session_id)
    if not session.audio_object_key:
        raise HTTPException(status_code=400, detail="Session has no uploaded audio")

    try:
        model = asr_proxy.AsrModel(body.model)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Unknown model: {body.model}") from e

    logger.info(
        "transcribe_session %s: starting (model=%s, object_key=%s)",
        session_id, model.value, session.audio_object_key,
    )
    import anyio

    os.makedirs(config.WORK_DIR, exist_ok=True)
    local_path = os.path.join(config.WORK_DIR, f"{session_id}.m4a")
    try:
        logger.info("transcribe_session %s: downloading audio ...", session_id)
        # boto3 has no asyncio support — download_to_path blocks the calling
        # thread for the whole transfer. Off the event loop via anyio (same
        # pattern as summarize_session below and auth.py's Firebase call),
        # so a large download doesn't stall every other concurrent request
        # (health checks, websocket streaming, other users) on this server.
        await anyio.to_thread.run_sync(
            storage.download_to_path, session.audio_object_key, local_path,
        )
        logger.info(
            "transcribe_session %s: downloaded %d bytes, calling ASR proxy ...",
            session_id, os.path.getsize(local_path),
        )
        try:
            result = await asr_proxy.transcribe(model, local_path, session.locale_id)
        except asr_proxy.AsrModelUnavailable as e:
            logger.warning("transcribe_session %s: model unavailable: %s", session_id, e)
            raise HTTPException(status_code=503, detail=str(e)) from e

        # Mutate through the ORM relationship (not a raw DELETE by
        # session_id) so the identity map stays consistent — see
        # replace_transcript()'s docstring in routers/sessions.py for why.
        session.transcript.clear()
        for seg in result.get("segments", []):
            session.transcript.append(
                TranscriptSegment(
                    text=seg["text"],
                    start_ms=seg["startMs"],
                    end_ms=seg.get("endMs", 0),
                    speaker=seg.get("speaker"),
                    is_final=seg.get("isFinal", True),
                )
            )
        session.status = session.status.__class__.transcribed

        # Runs against local_path while it still exists (cleaned up in the
        # finally block below) — separate try/except inside _match_speaker
        # so a speaker-embedding failure never fails the transcription
        # response it's riding along with. See that function's docstring
        # for the auto-confirm vs. suggest-only split.
        suggested_speaker = await _match_speaker(db, session, local_path)

        await db.commit()
        logger.info(
            "transcribe_session %s: done, %d segment(s) persisted",
            session_id, len(result.get("segments", [])),
        )
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

    out = _to_out(await _get_owned_session(db, user, session_id))
    out.suggestedSpeaker = suggested_speaker
    return out


@router.post("/{session_id}/summarize", response_model=schemas.KajianSessionOut)
async def summarize_session(
    session_id: str,
    body: schemas.SummarizeRequestIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    import datetime

    import anyio

    session = await _get_owned_session(db, user, session_id)
    plain_transcript = " ".join(
        seg.text.strip() for seg in session.transcript if seg.text.strip()
    )
    if not plain_transcript:
        raise HTTPException(status_code=400, detail="Session has no transcript yet")

    try:
        result = await anyio.to_thread.run_sync(
            notes.generate, plain_transcript, session.title, body.model
        )
    except Exception as e:  # noqa: BLE001 - surface as a clean 502, not a 500 stack trace
        raise HTTPException(status_code=502, detail=f"Summarize failed: {e}") from e

    # Delete-then-flush before reassigning — see replace_note()'s
    # docstring in routers/sessions.py for why this order matters (a
    # unique-constraint race between the old row's DELETE and the new
    # row's INSERT within the same flush otherwise).
    if session.note is not None:
        await db.delete(session.note)
        await db.flush()

    session.note = KajianNote(
        summary=result.get("summary", ""),
        key_points=result.get("keyPoints", []),
        topics=result.get("topics", []),
        action_items=result.get("actionItems", []),
        generated_at=datetime.datetime.now(datetime.timezone.utc),
        references=[
            ScriptureReference(
                type=ref.get("type", "quran"),
                citation=ref.get("citation", ""),
                note=ref.get("note"),
            )
            for ref in result.get("references", [])
        ],
    )
    session.status = session.status.__class__.completed
    await db.commit()

    return _to_out(await _get_owned_session(db, user, session_id))
