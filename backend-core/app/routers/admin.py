"""Admin-only API — backs the separate Next.js admin app (../admin/).

Every route here requires `current_admin` (see auth.py): a signed-in user
whose `is_admin` flag is set. There's no self-serve way to become an admin
through the API — see scripts/promote_admin.py.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import schemas
from ..auth import current_admin
from ..db import get_db
from ..models.kajian_note import KajianNote
from ..models.kajian_session import KajianSession
from ..models.user import User
from ..services import storage
from .sessions import _to_out

router = APIRouter(prefix="/admin", tags=["admin"])


class UserSummaryOut(BaseModel):
    id: str
    email: str | None
    displayName: str | None
    photoUrl: str | None
    isAdmin: bool
    createdAt: datetime
    lastSeenAt: datetime
    sessionCount: int


class StatsOut(BaseModel):
    userCount: int
    sessionCount: int
    completedSessionCount: int
    totalAudioDurationMs: int


@router.get("/stats", response_model=StatsOut)
async def stats(
    _admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)
) -> StatsOut:
    user_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    session_count = (
        await db.execute(select(func.count(KajianSession.id)))
    ).scalar_one()
    completed_count = (
        await db.execute(
            select(func.count(KajianSession.id)).where(
                KajianSession.status == "completed"
            )
        )
    ).scalar_one()
    total_duration = (
        await db.execute(select(func.coalesce(func.sum(KajianSession.duration_ms), 0)))
    ).scalar_one()
    return StatsOut(
        userCount=user_count,
        sessionCount=session_count,
        completedSessionCount=completed_count,
        totalAudioDurationMs=total_duration,
    )


@router.get("/users", response_model=list[UserSummaryOut])
async def list_users(
    _admin: User = Depends(current_admin), db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User, func.count(KajianSession.id))
        .outerjoin(KajianSession, KajianSession.user_id == User.id)
        .group_by(User.id)
        .order_by(User.created_at.desc())
    )
    return [
        UserSummaryOut(
            id=str(user.id),
            email=user.email,
            displayName=user.display_name,
            photoUrl=user.photo_url,
            isAdmin=user.is_admin,
            createdAt=user.created_at,
            lastSeenAt=user.last_seen_at,
            sessionCount=session_count,
        )
        for user, session_count in result.all()
    ]


@router.get("/users/{user_id}/sessions", response_model=list[schemas.KajianSessionOut])
async def list_user_sessions(
    user_id: str,
    _admin: User = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(KajianSession)
        .options(
            selectinload(KajianSession.transcript),
            selectinload(KajianSession.note).selectinload(KajianNote.references),
        )
        .where(KajianSession.user_id == user_id)
        .order_by(KajianSession.created_at.desc())
    )
    return [_to_out(s) for s in result.scalars().all()]


@router.get(
    "/sessions/{session_id}/audio-url", response_model=schemas.AudioDownloadUrlOut
)
async def admin_get_audio_url(
    session_id: str,
    _admin: User = Depends(current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Same as the user-facing GET /sessions/{id}/audio-url, but usable by
    an admin against any user's session (for support/moderation)."""
    result = await db.execute(
        select(KajianSession).where(KajianSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.audio_object_key:
        raise HTTPException(status_code=404, detail="No audio for this session")
    return schemas.AudioDownloadUrlOut(
        downloadUrl=storage.presigned_download_url(session.audio_object_key)
    )
