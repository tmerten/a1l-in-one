"""Person-centric API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_health.aggregation.core import Timeframe, build_timeframe
from project_health.aggregation.queries import (
    AggregationQueries,
    CommitsResponse,
    WorkItemsResponse,
)
from project_health.api.deps import get_config, get_registry, get_session
from project_health.config.loader import Config
from project_health.db.models import Sprint
from project_health.providers.registry import DataSourceRegistry

router = APIRouter()


async def _resolve_timeframe(
    session: AsyncSession,
    from_date: datetime | None,
    to_date: datetime | None,
    sprint_id: str | None,
    projects: list[str] | None = None,
    actors: list[str] | None = None,
) -> Timeframe:
    if sprint_id:
        result = await session.execute(select(Sprint).where(Sprint.id == sprint_id))
        sprint = result.scalar_one_or_none()
        if sprint:
            return Timeframe(
                kind="sprint",
                start=sprint.start_date,
                end=sprint.end_date,
                sprint_id=sprint_id,
                projects=projects,
                actors=actors,
            )
    return build_timeframe(from_date, to_date, sprint_id, projects=projects, actors=actors)


class IdentityInfo(BaseModel):
    source: str
    external_id: str
    display_name: str | None = None
    profile_url: str | None = None


class PersonMetrics(BaseModel):
    commits: int = 0
    prs_opened: int = 0
    prs_merged: int = 0
    pr_loc_added: int = 0
    pr_loc_removed: int = 0
    issues_resolved: int = 0
    issues_opened: int = 0
    reviews_given: int = 0
    review_comments: int = 0
    median_cycle_time_hours: float | None = None
    sources: dict[str, dict[str, Any]] = {}


class PersonSummary(BaseModel):
    id: str
    display_name: str
    identities: list[IdentityInfo]
    metrics: PersonMetrics


class PersonsResponse(BaseModel):
    persons: list[PersonSummary]


class ProjectContribution(BaseModel):
    project: str
    commits: int = 0
    pull_requests: int = 0
    pr_loc_added: int = 0
    pr_loc_removed: int = 0
    issues_resolved: int = 0
    issues_opened: int = 0
    reviews_given: int = 0


class DatasourceContribution(BaseModel):
    datasource: str
    role: str
    projects: list[ProjectContribution]


class PersonContributionsResponse(BaseModel):
    person_id: str
    display_name: str
    identities: list[IdentityInfo]
    timeframe: dict[str, Any]
    contributions: list[DatasourceContribution]


@router.get("/", response_model=PersonsResponse)
async def list_persons(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    sprint_id: str | None = Query(None),
    projects: list[str] | None = Query(None),
    datasource: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    config: Config = Depends(get_config),
    registry: DataSourceRegistry = Depends(get_registry),
) -> PersonsResponse:
    ctx = await _resolve_timeframe(session, from_date, to_date, sprint_id, projects=projects)
    configured_sources = registry.configured_sources()
    if datasource:
        configured_sources = configured_sources & {datasource}
    queries = AggregationQueries(session, config, configured_sources)
    persons = await queries.list_persons(ctx)
    return PersonsResponse(
        persons=[PersonSummary(**p) for p in persons]
    )


@router.get("/{person_id}/contributions", response_model=PersonContributionsResponse)
async def person_contributions(
    person_id: str,
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    sprint_id: str | None = Query(None),
    projects: list[str] | None = Query(None),
    session: AsyncSession = Depends(get_session),
    config: Config = Depends(get_config),
    registry: DataSourceRegistry = Depends(get_registry),
) -> PersonContributionsResponse:
    ctx = await _resolve_timeframe(session, from_date, to_date, sprint_id, projects=projects)
    configured_sources = registry.configured_sources()
    queries = AggregationQueries(session, config, configured_sources)
    result = await queries.person_contributions(person_id, ctx)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Person not found")
    return PersonContributionsResponse(**result)


@router.get("/{person_id}/work-items", response_model=WorkItemsResponse)
async def get_work_items(
    person_id: str,
    status: Literal["active", "completed"] = Query("completed"),
    datasource: str | None = Query(None),
    event_type: str | None = Query(None),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    config: Config = Depends(get_config),
    registry: DataSourceRegistry = Depends(get_registry),
) -> WorkItemsResponse:
    configured_sources = registry.configured_sources()
    if datasource:
        configured_sources = configured_sources & {datasource}

    queries = AggregationQueries(session, config, configured_sources)

    items, total = await queries.work_items(
        person_id=person_id,
        status=status,
        datasource=datasource,
        event_type=event_type,
        from_ts=from_date,
        to_ts=to_date,
        page=page,
        per_page=per_page,
    )

    return WorkItemsResponse(
        person_id=person_id,
        status=status,
        total=total,
        page=page,
        per_page=per_page,
        items=items,
    )


@router.get("/{person_id}/commits", response_model=CommitsResponse)
async def get_commits(
    person_id: str,
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    config: Config = Depends(get_config),
    registry: DataSourceRegistry = Depends(get_registry),
) -> CommitsResponse:
    configured_sources = registry.configured_sources()
    queries = AggregationQueries(session, config, configured_sources)

    items, total = await queries.commits(
        person_id=person_id,
        from_ts=from_date,
        to_ts=to_date,
        page=page,
        per_page=per_page,
    )

    return CommitsResponse(
        person_id=person_id,
        total=total,
        page=page,
        per_page=per_page,
        items=items,
    )
