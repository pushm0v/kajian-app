"""Firebase ID token verification, mapped to a local `User` row.

The Flutter app already signs in via Firebase Auth (Google/Apple) client-
side and can fetch a fresh ID token at any time
(`FirebaseAuth.instance.currentUser.getIdToken()`); it sends that as a
Bearer token on every API request. This module verifies it server-side —
Firebase stays the identity provider, this service owns the user's actual
data (sessions, transcripts, notes).

`auth.verify_id_token(...)` is a synchronous, network-free call in the
common case (it checks the JWT signature against Google's public certs,
which are cached in-process and refreshed every few hours per their own
Cache-Control headers) — it's run via `anyio.to_thread` here purely so a
slow cert-refetch on a cache miss can't block the event loop, not because
it's expected to be slow on every call.
"""

from __future__ import annotations

import anyio
import firebase_admin
from fastapi import Depends, HTTPException, Request
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import config
from .db import get_db
from .models.user import User

_firebase_app: firebase_admin.App | None = None


def init_firebase() -> None:
    """Call once at API startup (see main.py's lifespan). No-ops under
    CORE_DEV_AUTH_BYPASS, since there's nothing to verify against then."""
    global _firebase_app
    if config.DEV_AUTH_BYPASS or _firebase_app is not None:
        return
    cred = credentials.Certificate(config.FIREBASE_SERVICE_ACCOUNT_PATH)
    _firebase_app = firebase_admin.initialize_app(cred)


async def _verify_token(id_token: str) -> dict:
    if config.DEV_AUTH_BYPASS:
        raise RuntimeError("_verify_token should not be called under dev auth bypass")
    try:
        return await anyio.to_thread.run_sync(firebase_auth.verify_id_token, id_token)
    except firebase_auth.ExpiredIdTokenError as e:
        raise HTTPException(status_code=401, detail="Token expired") from e
    except firebase_auth.InvalidIdTokenError as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e
    except firebase_auth.CertificateFetchError as e:
        raise HTTPException(
            status_code=503, detail="Could not verify token (cert fetch failed)"
        ) from e


async def _get_or_create_user(
    db: AsyncSession, firebase_uid: str, email: str | None, name: str | None, picture: str | None
) -> User:
    result = await db.execute(select(User).where(User.firebase_uid == firebase_uid))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            firebase_uid=firebase_uid, email=email, display_name=name, photo_url=picture
        )
        db.add(user)
        await db.flush()
        return user

    # Keep the cached profile fields fresh (display name/photo can change on
    # the identity provider's side after the first sign-in).
    changed = False
    for field, value in (("email", email), ("display_name", name), ("photo_url", picture)):
        if value and getattr(user, field) != value:
            setattr(user, field, value)
            changed = True
    if changed:
        await db.flush()
    return user


async def current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    """FastAPI dependency: verifies the request's Bearer token and returns
    the corresponding (auto-provisioned) User row."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

    if config.DEV_AUTH_BYPASS:
        # DEV ONLY: trust the token value directly as a Firebase UID stand-in.
        # Never enable CORE_DEV_AUTH_BYPASS outside local development.
        return await _get_or_create_user(db, token, None, None, None)

    claims = await _verify_token(token)
    return await _get_or_create_user(
        db,
        firebase_uid=claims["uid"],
        email=claims.get("email"),
        name=claims.get("name"),
        picture=claims.get("picture"),
    )


async def current_admin(user: User = Depends(current_user)) -> User:
    """FastAPI dependency for admin-only endpoints (see routers/admin.py)."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def current_user_ws(token: str | None, db: AsyncSession) -> User:
    """Same verification as [current_user], for WebSocket routes.

    WebSocket clients can't reliably set custom headers during the
    handshake (browsers' WebSocket API in particular has no header API at
    all), so the token travels as a `?token=` query parameter instead — see
    routers/streaming.py. Raises HTTPException same as current_user; the
    caller is responsible for translating that into a WS close before
    accept() (FastAPI can't send a normal HTTP error response mid-handshake).
    """
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    if config.DEV_AUTH_BYPASS:
        return await _get_or_create_user(db, token, None, None, None)

    claims = await _verify_token(token)
    return await _get_or_create_user(
        db,
        firebase_uid=claims["uid"],
        email=claims.get("email"),
        name=claims.get("name"),
        picture=claims.get("picture"),
    )
