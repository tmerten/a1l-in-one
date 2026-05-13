"""FastAPI dependencies."""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from project_health.config.loader import Config
from project_health.db.session import get_session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session; closes on request teardown."""
    maker = get_session_maker()
    async with maker() as session:
        yield session


def get_config(request: Request) -> Config:
    """Return the app-level Config stored on app.state."""
    return request.app.state.config
