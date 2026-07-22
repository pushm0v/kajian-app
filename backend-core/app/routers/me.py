"""The signed-in user's own profile — separate from routers/sessions.py
since this is about the User row itself, not their kajian data."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import current_user
from ..models.user import User

router = APIRouter(prefix="/me", tags=["me"])


class UserOut(BaseModel):
    id: str
    email: str | None
    displayName: str | None
    photoUrl: str | None
    isAdmin: bool
    createdAt: datetime


@router.get("", response_model=UserOut)
async def get_me(user: User = Depends(current_user)) -> UserOut:
    return UserOut(
        id=str(user.id),
        email=user.email,
        displayName=user.display_name,
        photoUrl=user.photo_url,
        isAdmin=user.is_admin,
        createdAt=user.created_at,
    )
