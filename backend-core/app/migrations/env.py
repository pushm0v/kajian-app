"""Alembic environment. Uses a synchronous psycopg2 connection for running
migrations (simpler than juggling asyncpg inside Alembic's sync-oriented
runner), even though the app itself uses asyncpg at request time — see
app/db.py.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import config as app_config
from app.db import Base
from app.models import *  # noqa: F401,F403 - registers all models with Base.metadata

alembic_config = context.config
if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

target_metadata = Base.metadata


def _sync_database_url() -> str:
    # app_config.DATABASE_URL uses the asyncpg driver
    # (postgresql+asyncpg://...); Alembic's migration runner wants a
    # synchronous one.
    return app_config.DATABASE_URL.replace("+asyncpg", "+psycopg2")


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = alembic_config.get_section(alembic_config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _sync_database_url()
    connectable = engine_from_config(
        configuration, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
