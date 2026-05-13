"""FastAPI dependencies."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from project_health.db.session import get_session_maker


async def get_session() -> AsyncSession:
    """Yield an async database session."""
    maker = get_session_maker()
    async with maker() as session:
        return session
