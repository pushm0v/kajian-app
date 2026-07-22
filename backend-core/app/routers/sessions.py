"""CRUD for a signed-in user's own kajian sessions — the server-side
counterpart to the app's StorageService (which currently persists to a
local JSON file only; see lib/services/storage_service.dart).

Every route here is scoped to `current_user` — a user can only ever see or
modify their own sessions. There is no "list all sessions" route in this
file; that's an admin-only concern (see routers/admin.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import schemas
from ..auth import current_user
from ..db import get_db
from ..models.kajian_note import KajianNote, ScriptureReference
from ..models.kajian_session import KajianSession
from ..models.transcript_segment import TranscriptSegment
from ..models.user import User
from ..services import storage

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _to_out(session: KajianSession) -> schemas.KajianSessionOut:
    out = schemas.KajianSessionOut.model_validate(session)
    out.hasAudio = session.audio_object_key is not None
    return out


async def _get_owned_session(
    db: AsyncSession, user: User, session_id: str
) -> KajianSession:
    result = await db.execute(
        select(KajianSession)
        .options(
            selectinload(KajianSession.transcript),
            selectinload(KajianSession.note).selectinload(KajianNote.references),
        )
        .where(KajianSession.id == session_id, KajianSession.user_id == user.id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("", response_model=list[schemas.KajianSessionOut])
async def list_sessions(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(KajianSession)
        .options(
            selectinload(KajianSession.transcript),
            selectinload(KajianSession.note).selectinload(KajianNote.references),
        )
        .where(KajianSession.user_id == user.id)
        .order_by(KajianSession.created_at.desc())
    )
    return [_to_out(s) for s in result.scalars().all()]


@router.post("", response_model=schemas.KajianSessionOut, status_code=201)
async def create_session(
    body: schemas.SessionCreateIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    session = KajianSession(
        id=body.id,
        user_id=user.id,
        title=body.title,
        speaker=body.speaker,
        location=body.location,
        created_at=body.createdAt,
        duration_ms=body.durationMs,
        locale_id=body.localeId,
        status=body.status,
    )
    db.add(session)
    await db.commit()
    return _to_out(await _get_owned_session(db, user, session.id))


@router.patch("/{session_id}", response_model=schemas.KajianSessionOut)
async def update_session(
    session_id: str,
    body: schemas.SessionUpdateIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, user, session_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        column = {
            "title": "title",
            "speaker": "speaker",
            "location": "location",
            "durationMs": "duration_ms",
            "status": "status",
        }[field]
        setattr(session, column, value)
    await db.commit()
    return _to_out(await _get_owned_session(db, user, session_id))


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, user, session_id)
    if session.audio_object_key:
        storage.delete_object(session.audio_object_key)
    await db.execute(delete(KajianSession).where(KajianSession.id == session_id))
    await db.commit()


@router.put("/{session_id}/transcript", response_model=schemas.KajianSessionOut)
async def replace_transcript(
    session_id: str,
    body: schemas.TranscriptReplaceIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Wholesale replace — matches the app's own model, which always
    produces a complete new transcript list per transcription pass rather
    than incrementally patching individual segments.

    Mutates `session.transcript` through the ORM relationship (not a raw
    delete()+add() by session_id) so SQLAlchemy's identity map stays
    consistent — a bulk DELETE outside the relationship's own tracking
    leaves the already-loaded `session` object's cached `.transcript`
    collection stale for the rest of this request/session.
    """
    session = await _get_owned_session(db, user, session_id)
    session.transcript.clear()
    for seg in body.segments:
        session.transcript.append(
            TranscriptSegment(
                text=seg.text,
                start_ms=seg.startMs,
                end_ms=seg.endMs,
                speaker=seg.speaker,
                is_final=seg.isFinal,
            )
        )
    await db.commit()
    return _to_out(await _get_owned_session(db, user, session_id))


@router.put("/{session_id}/note", response_model=schemas.KajianSessionOut)
async def replace_note(
    session_id: str,
    body: schemas.KajianNoteIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    import datetime

    # Assigned through the ORM relationship (not a separate db.add() with a
    # manually-set session_id) for identity-map consistency — same reason
    # as replace_transcript() above. The old note is explicitly deleted
    # and flushed *before* assigning the new one: session.note's unique
    # session_id constraint means simply reassigning session.note = new
    # note in one flush can race the DELETE-then-INSERT ordering within
    # that single unit of work and hit a unique-violation, since the old
    # row hasn't been removed yet when the new one is inserted.
    session = await _get_owned_session(db, user, session_id)
    if session.note is not None:
        await db.delete(session.note)
        await db.flush()

    session.note = KajianNote(
        summary=body.summary,
        key_points=body.keyPoints,
        topics=body.topics,
        action_items=body.actionItems,
        generated_at=datetime.datetime.now(datetime.timezone.utc),
        references=[
            ScriptureReference(type=ref.type, citation=ref.citation, note=ref.note)
            for ref in body.references
        ],
    )
    await db.commit()
    return _to_out(await _get_owned_session(db, user, session_id))


@router.post("/{session_id}/audio-upload-url", response_model=schemas.AudioUploadUrlOut)
async def get_audio_upload_url(
    session_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mints a presigned PUT URL the app uploads the recorded .m4a directly
    to (bypassing this API's own bandwidth). Call POST /sessions/{id}/audio-
    confirm once the upload finishes, so the DB row knows audio exists."""
    session = await _get_owned_session(db, user, session_id)
    object_key = storage.object_key_for_session(str(user.id), session.id)
    return schemas.AudioUploadUrlOut(
        uploadUrl=storage.presigned_upload_url(object_key), objectKey=object_key
    )


@router.post("/{session_id}/audio-confirm", response_model=schemas.KajianSessionOut)
async def confirm_audio_uploaded(
    session_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, user, session_id)
    session.audio_object_key = storage.object_key_for_session(str(user.id), session.id)
    await db.commit()
    return _to_out(await _get_owned_session(db, user, session_id))


@router.get("/{session_id}/audio-url", response_model=schemas.AudioDownloadUrlOut)
async def get_audio_download_url(
    session_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, user, session_id)
    if not session.audio_object_key:
        raise HTTPException(status_code=404, detail="No audio for this session")
    return schemas.AudioDownloadUrlOut(
        downloadUrl=storage.presigned_download_url(session.audio_object_key)
    )
