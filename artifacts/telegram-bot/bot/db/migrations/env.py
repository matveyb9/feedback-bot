"""
Alembic env.py — async-конфигурация для PostgreSQL через asyncpg.
Не требует дополнительного sync-драйвера (psycopg2).
"""
import asyncio
import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Импортируем Base и все модели, чтобы autogenerate видел их метаданные
from bot.db.base import Base
import bot.db.models  # noqa: F401  — side-effect import, регистрирует таблицы

config = context.config
fileConfig(config.config_file_name)  # type: ignore[arg-type]

target_metadata = Base.metadata


def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL не задана — Alembic не может подключиться к БД")
    # Гарантируем asyncpg-драйвер
    url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def do_run_migrations(connection: Any) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(_get_database_url(), echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


run_migrations_online()
