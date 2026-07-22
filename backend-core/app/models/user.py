"""A user of the app, identified by their Firebase UID.

Rows are auto-provisioned on a user's first authenticated request (see
app/auth.py) — there's no separate sign-up flow here, since Firebase Auth
(already wired up client-side in the Flutter app) is the identity provider.
This table exists so the rest of the schema (sessions, notes, audio) has a
stable foreign key that survives even if the user's Firebase profile data
(display name, photo) changes.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    firebase_uid: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # Admin dashboard access. Not settable via the app's own API — see
    # scripts/promote_admin.py for how to grant this.
    is_admin: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list["KajianSession"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
