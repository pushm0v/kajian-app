"""Pydantic request/response models for the API.

Field names match the Flutter app's JSON exactly (camelCase, matching
lib/models/*.dart's toJson()/fromJson()) rather than Python's snake_case
convention, so the app needs no key-renaming logic on either side of the
wire — this is a public API contract, not internal Python code.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from .models.kajian_session import SessionStatus

# The app's TranscriptSegment.id (and the request bodies that create one)
# is always a plain string, but the DB-generated primary key is a real
# uuid.UUID object — coerce it to str on the way out rather than typing
# these fields as `str` and having Pydantic reject the ORM's UUID value.
_IdStr = Annotated[str, BeforeValidator(str)]


class TranscriptSegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: _IdStr
    text: str
    startMs: int = Field(validation_alias="start_ms", serialization_alias="startMs")
    endMs: int = Field(validation_alias="end_ms", serialization_alias="endMs")
    speaker: str | None = None
    isFinal: bool = Field(validation_alias="is_final", serialization_alias="isFinal")


class ScriptureReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    type: str
    citation: str
    note: str | None = None


class KajianNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary: str
    keyPoints: list[str] = Field(validation_alias="key_points", serialization_alias="keyPoints")
    topics: list[str] = []
    references: list[ScriptureReferenceOut] = []
    actionItems: list[str] = Field(
        validation_alias="action_items", serialization_alias="actionItems"
    )
    generatedAt: datetime = Field(
        validation_alias="generated_at", serialization_alias="generatedAt"
    )


class SuggestedSpeakerOut(BaseModel):
    """A voice-fingerprint match, surfaced for the user to confirm or
    reject — never auto-assigned. See services/speaker_matching.py."""

    speakerId: str
    name: str
    score: float


class KajianSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    speaker: str | None = None
    # Links to a confirmed Speaker profile, once one exists — null until
    # the user confirms a suggestion (or an exact-name auto-match fires).
    speakerId: Annotated[str | None, BeforeValidator(lambda v: str(v) if v is not None else None)] = Field(
        default=None, validation_alias="speaker_id", serialization_alias="speakerId",
    )
    location: str | None = None
    createdAt: datetime = Field(validation_alias="created_at", serialization_alias="createdAt")
    durationMs: int = Field(validation_alias="duration_ms", serialization_alias="durationMs")
    localeId: str = Field(validation_alias="locale_id", serialization_alias="localeId")
    status: SessionStatus
    # Set when a background transcribe/summarize job fails (status becomes
    # `error`) — see routers/processing.py's _run_transcription. Null
    # otherwise, including after a successful retry (cleared on each new
    # attempt).
    errorMessage: str | None = Field(
        default=None, validation_alias="error_message", serialization_alias="errorMessage",
    )
    transcript: list[TranscriptSegmentOut] = []
    note: KajianNoteOut | None = None
    # True if audio was ever uploaded for this session — the app checks this
    # rather than getting a raw object key, since it must ask this API for
    # a fresh presigned URL each time it actually needs to play/re-process
    # the audio (see GET /sessions/{id}/audio-url). Not present on the ORM
    # model at all — deliberately defaulted here and always set explicitly
    # by _to_out() after model_validate(), rather than sourced via an alias,
    # since it's derived (audio_object_key is not None), not a real column.
    hasAudio: bool = False
    # Same pattern as hasAudio — not an ORM column, only ever set (by
    # transcribe_session, see routers/processing.py) right after a fresh
    # transcription's embedding comparison runs. Absent/null everywhere
    # else, including on every other route that returns a KajianSessionOut.
    suggestedSpeaker: SuggestedSpeakerOut | None = None


class SessionCreateIn(BaseModel):
    id: str
    title: str
    speaker: str | None = None
    location: str | None = None
    createdAt: datetime
    durationMs: int = 0
    localeId: str = "id_ID"
    status: SessionStatus = SessionStatus.recorded


class SessionUpdateIn(BaseModel):
    title: str | None = None
    speaker: str | None = None
    location: str | None = None
    durationMs: int | None = None
    status: SessionStatus | None = None


class TranscriptSegmentIn(BaseModel):
    id: str
    text: str
    startMs: int
    endMs: int = 0
    speaker: str | None = None
    isFinal: bool = True


class TranscriptReplaceIn(BaseModel):
    segments: list[TranscriptSegmentIn]


class ScriptureReferenceIn(BaseModel):
    type: str
    citation: str
    note: str | None = None


class KajianNoteIn(BaseModel):
    summary: str
    keyPoints: list[str] = []
    topics: list[str] = []
    references: list[ScriptureReferenceIn] = []
    actionItems: list[str] = []


class AudioUploadUrlOut(BaseModel):
    uploadUrl: str
    objectKey: str


class AudioDownloadUrlOut(BaseModel):
    downloadUrl: str


class TranscribeRequestIn(BaseModel):
    # "whisper" | "qwen". Whisper is the default: the Qwen worker holds
    # GPU device 0, which the dedicated speaker embedding service
    # (../backend-embedding/) now needs, so Qwen is expected to be stopped
    # in this deployment. It stays selectable for callers that still have
    # that worker running.
    model: str = "whisper"
    # Optional overrides for the speaker-embedding step, passed through to
    # the embedding service's /embed-speaker. Empty/omitted means "use
    # that service's own default". Exposed so the dev-console can toggle
    # per-request without restarting any container.
    #
    # provider: "cpu" | "cuda" (service default: cuda — it has its own GPU)
    # model:    "campplus" | "eres2netv2" (service default: campplus, the
    #           only multilingual checkpoint available; see that service's
    #           config.py for why that matters for Indonesian audio)
    speakerEmbeddingProvider: str = ""
    speakerEmbeddingModel: str = ""


class SummarizeRequestIn(BaseModel):
    model: str | None = None


class SpeakerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: _IdStr
    name: str
    embeddingCount: int = Field(validation_alias="embedding_count", serialization_alias="embeddingCount")
    createdAt: datetime = Field(validation_alias="created_at", serialization_alias="createdAt")


class SpeakerConfirmIn(BaseModel):
    # Exactly one of these — confirm an existing suggested/known speaker by
    # id, or create a brand-new profile from this session's embedding under
    # a fresh name. Enforced in the route handler, not here (a Pydantic
    # validator would need to reject on missing-both AND both-present,
    # which reads less clearly than one explicit if/elif in the handler).
    speakerId: str | None = None
    newSpeakerName: str | None = None
