"""POST /sessions/{id}/transcribe and /summarize — orchestrates the
existing ASR workers (../backend/, ../backend-whisper/) and the Anthropic
notes service against a session's already-uploaded audio, persisting the
result directly rather than round-tripping it back to the app first.

This replaces the app's own SessionProvider.process() pipeline: the app
now asks the server to do the work and polls/reads back the updated
session, instead of calling CloudTranscriptionService/AiNotesService
directly and pushing the result up itself.

Both /transcribe and /summarize run as FastAPI BackgroundTasks rather
than blocking the request: a real recording can take minutes to
transcribe (download + ASR inference + speaker-embedding extraction, all
chained in one job), and holding an HTTP response open that long hits
hard, non-configurable proxy limits before it ever reaches this process —
Cloudflare's Proxy Read Timeout is a fixed 125s on every plan below
Enterprise, confirmed against this exact deploy (a 44-minute recording's
transcribe request failed client-side at ~125s elapsed, even after
raising Traefik's own timeout, which is a *different, more generous*
limit — Cloudflare's edge cuts the connection before Traefik's extended
window ever matters). Both endpoints now return immediately (202,
status=transcribing/summarizing) and the caller polls GET
/sessions/{id} (see routers/sessions.py) until status moves to its
terminal state (transcribed/completed) or error (see
KajianSession.error_message).

Background tasks run in this same process (no separate queue/worker
infra exists in this codebase) using their own fresh DB session from
db.SessionLocal — the request-scoped `db` session dependency is closed
once the response is sent, so the background function cannot reuse it.
"""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import config, schemas
from ..auth import current_user
from ..db import SessionLocal, get_db
from ..models.kajian_note import KajianNote, ScriptureReference
from ..models.kajian_session import KajianSession, SessionStatus
from ..models.speaker import Speaker
from ..models.transcript_segment import TranscriptSegment
from ..models.user import User
from ..services import asr_proxy, notes, storage
from ..services.speaker_matching import find_best_match, update_centroid
from .sessions import _get_owned_session, _to_out

logger = logging.getLogger("kajian_core")

router = APIRouter(prefix="/sessions", tags=["processing"])


async def _match_speaker(
    db: AsyncSession, session: KajianSession, local_path: str, embedding_provider: str = "",
) -> None:
    """Extracts a speaker embedding for `session` and either auto-confirms
    it (exact, case-insensitive match against session.speaker's typed
    name) or stashes it as session.pending_embedding for the user to
    confirm later via POST /sessions/{id}/speaker-confirm — never both,
    never neither. The suggestion itself isn't returned here (unlike the
    old synchronous version) since this now runs in the background with
    no request/response to attach it to — GET /sessions/{id} doesn't
    surface a "suggestion" field, only the persisted pending_embedding/
    speaker_id state; a future enhancement could compute+expose the
    suggestion on read instead of only at transcribe-time, if that's
    wanted.

    Failures here are logged and swallowed: a speaker-embedding problem
    should never fail the transcription job it's riding along with.
    """
    try:
        embedding = await asr_proxy.embed_speaker(local_path, embedding_provider)
    except Exception:  # noqa: BLE001 - best-effort; transcription already succeeded
        logger.exception("transcribe_session %s: speaker embedding failed, skipping", session.id)
        return

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
            return

    match = find_best_match(embedding, candidates)
    session.pending_embedding = embedding
    if match is None:
        logger.info("transcribe_session %s: no speaker match above threshold", session.id)
        return

    speaker, score = match
    logger.info(
        "transcribe_session %s: suggesting speaker=%s (score=%.3f)", session.id, speaker.id, score,
    )


async def _run_transcription(
    session_id: str, user_id, model_value: str, speaker_embedding_provider: str,
) -> None:
    """The actual transcribe job — download, ASR proxy, speaker embedding,
    persist. Runs as a BackgroundTask (see transcribe_session below), so
    it opens its own DB session rather than reusing the request-scoped one
    (already closed by the time this runs).
    """
    async with SessionLocal() as db:
        result = await db.execute(
            select(KajianSession).where(
                KajianSession.id == session_id, KajianSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            logger.error("_run_transcription %s: session vanished before job started", session_id)
            return

        try:
            model = asr_proxy.AsrModel(model_value)
        except ValueError:
            session.status = SessionStatus.error
            session.error_message = f"Unknown model: {model_value}"
            await db.commit()
            return

        logger.info(
            "transcribe_session %s: starting (model=%s, object_key=%s)",
            session_id, model.value, session.audio_object_key,
        )

        import anyio

        os.makedirs(config.WORK_DIR, exist_ok=True)
        local_path = os.path.join(config.WORK_DIR, f"{session_id}.m4a")
        try:
            logger.info("transcribe_session %s: downloading audio ...", session_id)
            # boto3 has no asyncio support — download_to_path blocks the
            # calling thread for the whole transfer. Off the event loop
            # via anyio so a large download doesn't stall other requests
            # this process is handling concurrently.
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
                session.status = SessionStatus.error
                session.error_message = str(e)
                await db.commit()
                return

            # Mutate through the ORM relationship (not a raw DELETE by
            # session_id) so the identity map stays consistent — see
            # replace_transcript()'s docstring in routers/sessions.py.
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
            session.status = SessionStatus.transcribed
            session.error_message = None

            # Runs against local_path while it still exists (cleaned up in
            # the finally block below) — its own try/except inside
            # _match_speaker so a speaker-embedding failure never fails
            # the transcription job it's riding along with.
            await _match_speaker(db, session, local_path, speaker_embedding_provider)

            await db.commit()
            logger.info(
                "transcribe_session %s: done, %d segment(s) persisted",
                session_id, len(result.get("segments", [])),
            )
        except Exception as e:  # noqa: BLE001 - background task has no caller to raise to
            logger.exception("transcribe_session %s: failed", session_id)
            session.status = SessionStatus.error
            session.error_message = str(e)
            await db.commit()
        finally:
            if os.path.exists(local_path):
                os.remove(local_path)


@router.post("/{session_id}/transcribe", response_model=schemas.KajianSessionOut, status_code=202)
async def transcribe_session(
    session_id: str,
    body: schemas.TranscribeRequestIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, user, session_id)
    if not session.audio_object_key:
        raise HTTPException(status_code=400, detail="Session has no uploaded audio")

    try:
        asr_proxy.AsrModel(body.model)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Unknown model: {body.model}") from e

    session.status = SessionStatus.transcribing
    session.error_message = None
    await db.commit()

    background_tasks.add_task(
        _run_transcription, session_id, user.id, body.model, body.speakerEmbeddingProvider,
    )
    logger.info("transcribe_session %s: scheduled as background task", session_id)

    return _to_out(await _get_owned_session(db, user, session_id))


async def _run_summarization(session_id: str, user_id, model: str | None) -> None:
    """The actual summarize job. Runs as a BackgroundTask, own DB session
    — same reasoning as _run_transcription above."""
    import datetime

    async with SessionLocal() as db:
        result = await db.execute(
            select(KajianSession).where(
                KajianSession.id == session_id, KajianSession.user_id == user_id,
            )
        )
        session = result.scalar_one_or_none()
        if session is None:
            logger.error("_run_summarization %s: session vanished before job started", session_id)
            return

        plain_transcript = " ".join(
            seg.text.strip() for seg in session.transcript if seg.text.strip()
        )
        if not plain_transcript:
            session.status = SessionStatus.error
            session.error_message = "Session has no transcript yet"
            await db.commit()
            return

        try:
            import anyio

            result_data = await anyio.to_thread.run_sync(
                notes.generate, plain_transcript, session.title, model
            )
        except Exception as e:  # noqa: BLE001 - background task has no caller to raise to
            logger.exception("summarize_session %s: failed", session_id)
            session.status = SessionStatus.error
            session.error_message = f"Summarize failed: {e}"
            await db.commit()
            return

        # Delete-then-flush before reassigning — see replace_note()'s
        # docstring in routers/sessions.py for why this order matters (a
        # unique-constraint race between the old row's DELETE and the new
        # row's INSERT within the same flush otherwise).
        if session.note is not None:
            await db.delete(session.note)
            await db.flush()

        session.note = KajianNote(
            summary=result_data.get("summary", ""),
            key_points=result_data.get("keyPoints", []),
            topics=result_data.get("topics", []),
            action_items=result_data.get("actionItems", []),
            generated_at=datetime.datetime.now(datetime.timezone.utc),
            references=[
                ScriptureReference(
                    type=ref.get("type", "quran"),
                    citation=ref.get("citation", ""),
                    note=ref.get("note"),
                )
                for ref in result_data.get("references", [])
            ],
        )
        session.status = SessionStatus.completed
        session.error_message = None
        await db.commit()
        logger.info("summarize_session %s: done", session_id)


@router.post("/{session_id}/summarize", response_model=schemas.KajianSessionOut, status_code=202)
async def summarize_session(
    session_id: str,
    body: schemas.SummarizeRequestIn,
    background_tasks: BackgroundTasks,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_owned_session(db, user, session_id)
    plain_transcript = " ".join(
        seg.text.strip() for seg in session.transcript if seg.text.strip()
    )
    if not plain_transcript:
        raise HTTPException(status_code=400, detail="Session has no transcript yet")

    session.status = SessionStatus.summarizing
    session.error_message = None
    await db.commit()

    background_tasks.add_task(_run_summarization, session_id, user.id, body.model)
    logger.info("summarize_session %s: scheduled as background task", session_id)

    return _to_out(await _get_owned_session(db, user, session_id))
