"""Projects API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_health.api.deps import get_session
from project_health.db.models import RawEvent, Sprint

router = APIRouter()


class ProjectsResponse(BaseModel):
    projects: list[str]


@router.get("/")
async def list_projects(
    session: AsyncSession = Depends(get_session),
) -> ProjectsResponse:
    """Return distinct projects from raw events and sprints."""
    raw_result = await session.execute(
        select(RawEvent.project).where(RawEvent.project.isnot(None)).distinct()
    )
    raw_projects = {row[0] for row in raw_result.all() if row[0]}

    sprint_result = await session.execute(select(Sprint.project).distinct())
    sprint_projects = {row[0] for row in sprint_result.all() if row[0]}

    all_projects = sorted(raw_projects | sprint_projects)
    return ProjectsResponse(projects=all_projects)
