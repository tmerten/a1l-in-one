"""Database connection and session management."""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DEFAULT_DB_URL = "sqlite+aiosqlite:///./project_health.db"

_DATABASE_URL: str | None = None
_engine = None
_session_maker = None


def get_database_url() -> str:
    """Return the configured database URL."""
    if _DATABASE_URL is not None:
        return _DATABASE_URL
    return os.environ.get("DATABASE_URL", DEFAULT_DB_URL)


def set_database_url(url: str) -> None:
    """Override the database URL (used by tests)."""
    global _DATABASE_URL, _engine, _session_maker
    _DATABASE_URL = url
    _engine = None
    _session_maker = None


def get_engine():
    """Lazy-create the async engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_database_url(), echo=False, future=True)
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """Lazy-create the async session maker."""
    global _session_maker
    if _session_maker is None:
        _session_maker = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_maker


async def get_session() -> AsyncSession:
    """Yield an async session."""
    maker = get_session_maker()
    async with maker() as session:
        return session
