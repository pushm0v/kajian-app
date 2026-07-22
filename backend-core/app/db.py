"""Database engine/session setup (SQLAlchemy 2.0, async)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from . import config


class Base(DeclarativeBase):
    pass


engine = create_async_engine(config.DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:  # FastAPI dependency
    async with SessionLocal() as session:
        yield session
