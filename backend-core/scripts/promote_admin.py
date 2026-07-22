#!/usr/bin/env python3
"""Grants admin access to a user, by email.

There's deliberately no API route for this — an admin flag shouldn't be
settable through the same API a compromised client could call. Run this
directly against the database instead:

    python scripts/promote_admin.py someone@example.com

The user must have signed into the app at least once already (their row
is auto-provisioned on first authenticated request — see app/auth.py).
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

sys.path.insert(0, "..")  # allow running from backend-core/ or scripts/

from app.db import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402


async def main(email: str) -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"No user found with email {email!r}. Have they signed in yet?")
            raise SystemExit(1)
        user.is_admin = True
        await db.commit()
        print(f"Granted admin access to {email} (user id: {user.id})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(1)
    asyncio.run(main(sys.argv[1]))
