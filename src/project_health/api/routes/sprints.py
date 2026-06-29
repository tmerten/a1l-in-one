"""Sprints API endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_health.api.deps import get_session
from project_health.db.models import Sprint

router = APIRouter()


class SprintResponse(BaseModel):
    id: str
    name: str
    project: str
    start_date: datetime
    end_date: datetime
    state: str
    is_active: bool


@router.get("/")
async def list_sprints(
    project: str | None = Query(None),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[SprintResponse]:
    """List sprints for a project.

    Returns all active/future sprints plus the most recent closed ones,
    up to *limit* total entries (default 20).
    """
    stmt = select(Sprint).order_by(Sprint.end_date.desc())
    if project:
        stmt = stmt.where(Sprint.project == project)
    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    return [
        SprintResponse(
            id=row.id,
            name=row.name,
            project=row.project,
            start_date=row.start_date,
            end_date=row.end_date,
            state=row.state,
            is_active=row.state == "active",
        )
        for row in rows
    ]
