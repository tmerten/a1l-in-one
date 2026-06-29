"""Projects API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_health.api.deps import get_registry, get_session
from project_health.db.models import RawEvent, Sprint
from project_health.providers.registry import DataSourceRegistry

router = APIRouter()


class DatasourceProjectGroup(BaseModel):
    id: str
    role: str
    display_name: str
    projects: list[str]
    bug_targets: list[str] = []
    repositories: list[str] = []


class GroupedProjectsResponse(BaseModel):
    datasources: list[DatasourceProjectGroup]


class ProjectsResponse(BaseModel):
    projects: list[str]


@router.get("/")
async def list_projects(
    format: str = Query("grouped", alias="format"),
    session: AsyncSession = Depends(get_session),
    registry: DataSourceRegistry = Depends(get_registry),
) -> GroupedProjectsResponse | ProjectsResponse:
    if format == "flat":
        raw_result = await session.execute(
            select(RawEvent.project).where(RawEvent.project.isnot(None)).distinct()
        )
        raw_projects = {row[0] for row in raw_result.all() if row[0]}
        sprint_result = await session.execute(select(Sprint.project).distinct())
        sprint_projects = {row[0] for row in sprint_result.all() if row[0]}
        all_projects = sorted(raw_projects | sprint_projects)
        return ProjectsResponse(projects=all_projects)

    datasources = [
        DatasourceProjectGroup(
            id=ds.id,
            role=ds.role.value,
            display_name=ds.display_name,
            projects=ds.projects,
            bug_targets=ds.bug_targets,
            repositories=ds.repositories,
        )
        for ds in registry.datasources
        if ds.is_configured
    ]
    return GroupedProjectsResponse(datasources=datasources)
