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

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .. import config, schemas
from ..auth import current_user
from ..db import get_db
from ..models.kajian_note import KajianNote, ScriptureReference
from ..models.transcript_segment import TranscriptSegment
from ..models.user import User
from ..services import asr_proxy, notes, storage
from .sessions import _get_owned_session, _to_out

router = APIRouter(prefix="/sessions", tags=["processing"])


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

    os.makedirs(config.WORK_DIR, exist_ok=True)
    local_path = os.path.join(config.WORK_DIR, f"{session_id}.m4a")
    try:
        storage.download_to_path(session.audio_object_key, local_path)
        try:
            result = await asr_proxy.transcribe(model, local_path, session.locale_id)
        except asr_proxy.AsrModelUnavailable as e:
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
        await db.commit()
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

    return _to_out(await _get_owned_session(db, user, session_id))


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
