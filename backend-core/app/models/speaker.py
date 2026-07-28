"""A confirmed voice profile: a name plus a running-average embedding
centroid, built up from confirmed matches across sessions.

Global (not per-user) — a self-hosted instance's whole community shares one
speaker library, so the same ustadz recorded by different users still
resolves to the same profile. See KajianSession.speaker_id for how a
session links to a confirmed profile, and KajianSession.speaker (the
existing free-text field) for the pre-confirmation, user-typed label.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, index=True)

    # Running-average embedding centroid (192-dim, from sherpa-onnx's CAM++
    # model — see app/services/speaker_matching.py). Updated on every
    # confirmed enrollment via incremental averaging, not replaced, so a
    # single noisy recording can't overwrite an otherwise-good profile.
    embedding: Mapped[list[float]] = mapped_column(ARRAY(Float))
    embedding_count: Mapped[int] = mapped_column(default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list["KajianSession"]] = relationship(  # noqa: F821
        back_populates="speaker_profile"
    )
