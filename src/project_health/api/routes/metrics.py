"""Metrics aggregation API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_health.aggregation.core import Timeframe, build_timeframe
from project_health.aggregation.queries import AggregationQueries
from project_health.api.deps import get_config, get_session
from project_health.config.loader import Config
from project_health.db.models import Sprint

router = APIRouter()


async def _resolve_timeframe(
    session: AsyncSession,
    from_date: datetime | None,
    to_date: datetime | None,
    sprint_id: str | None,
    projects: list[str] | None = None,
    actors: list[str] | None = None,
) -> Timeframe:
    """Resolve sprint_id to date range if provided, else fall back to build_timeframe."""
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


class ContributionVolumeResponse(BaseModel):
    commits: int
    pull_requests: int
    additions: int
    deletions: int
    issues_opened: int
    issues_resolved: int
    internal_ratio: float
    external_ratio: float
    per_source: dict[str, dict[str, Any]]


class VelocityResponse(BaseModel):
    cycle_time_median: float | None
    cycle_time_p50: float | None
    cycle_time_p90: float | None
    review_turnaround_median: float | None
    review_turnaround_p50: float | None
    review_turnaround_p90: float | None
    per_source: dict[str, dict[str, Any]]


class CompositionResponse(BaseModel):
    issue_types: dict[str, int]
    pr_sizes: dict[str, int]
    per_source: dict[str, dict[str, Any]]


class CollaborationResponse(BaseModel):
    review_matrix: dict[str, dict[str, int]]
    per_person: dict[str, dict[str, Any]]


class SprintBurndownResponse(BaseModel):
    committed: int | float
    completed: int | float
    carried_over: int | float
    unit: str


@router.get("/contribution-volume")
async def contribution_volume(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    sprint_id: str | None = Query(None),
    projects: list[str] | None = Query(None),
    actors: list[str] | None = Query(None),
    session: AsyncSession = Depends(get_session),
    config: Config = Depends(get_config),
) -> ContributionVolumeResponse:
    ctx = await _resolve_timeframe(session, from_date, to_date, sprint_id, projects, actors)
    queries = AggregationQueries(session, config)
    result = await queries.contribution_volume(ctx)
    return ContributionVolumeResponse(**result)


@router.get("/velocity")
async def velocity(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    sprint_id: str | None = Query(None),
    projects: list[str] | None = Query(None),
    actors: list[str] | None = Query(None),
    session: AsyncSession = Depends(get_session),
    config: Config = Depends(get_config),
) -> VelocityResponse:
    ctx = await _resolve_timeframe(session, from_date, to_date, sprint_id, projects, actors)
    queries = AggregationQueries(session, config)
    result = await queries.velocity(ctx)
    return VelocityResponse(**result)


@router.get("/composition")
async def composition(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    sprint_id: str | None = Query(None),
    projects: list[str] | None = Query(None),
    actors: list[str] | None = Query(None),
    session: AsyncSession = Depends(get_session),
    config: Config = Depends(get_config),
) -> CompositionResponse:
    ctx = await _resolve_timeframe(session, from_date, to_date, sprint_id, projects, actors)
    queries = AggregationQueries(session, config)
    result = await queries.composition(ctx)
    return CompositionResponse(**result)


@router.get("/collaboration")
async def collaboration(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    sprint_id: str | None = Query(None),
    projects: list[str] | None = Query(None),
    actors: list[str] | None = Query(None),
    session: AsyncSession = Depends(get_session),
    config: Config = Depends(get_config),
) -> CollaborationResponse:
    ctx = await _resolve_timeframe(session, from_date, to_date, sprint_id, projects, actors)
    queries = AggregationQueries(session, config)
    result = await queries.collaboration(ctx)
    return CollaborationResponse(**result)


@router.get("/sprint-burndown")
async def sprint_burndown(
    sprint_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
    config: Config = Depends(get_config),
) -> SprintBurndownResponse:
    queries = AggregationQueries(session, config)
    result = await queries.sprint_burndown(sprint_id)
    return SprintBurndownResponse(**result)


# Time-series variants

class TimeSeriesPoint(BaseModel):
    bucket: str
    value: dict[str, Any]


class TimeSeriesResponse(BaseModel):
    bucket_size: str
    data: list[TimeSeriesPoint]


@router.get("/contribution-volume/ts")
async def contribution_volume_ts(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    sprint_id: str | None = Query(None),
    projects: list[str] | None = Query(None),
    actors: list[str] | None = Query(None),
    session: AsyncSession = Depends(get_session),
    config: Config = Depends(get_config),
) -> TimeSeriesResponse:
    ctx = await _resolve_timeframe(session, from_date, to_date, sprint_id, projects, actors)
    queries = AggregationQueries(session, config)
    result = await queries.contribution_volume_ts(ctx)
    return TimeSeriesResponse(**result)


@router.get("/velocity/ts")
async def velocity_ts(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    sprint_id: str | None = Query(None),
    projects: list[str] | None = Query(None),
    actors: list[str] | None = Query(None),
    session: AsyncSession = Depends(get_session),
    config: Config = Depends(get_config),
) -> TimeSeriesResponse:
    ctx = await _resolve_timeframe(session, from_date, to_date, sprint_id, projects, actors)
    queries = AggregationQueries(session, config)
    result = await queries.velocity_ts(ctx)
    return TimeSeriesResponse(**result)


@router.get("/collaboration/ts")
async def collaboration_ts(
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    sprint_id: str | None = Query(None),
    projects: list[str] | None = Query(None),
    actors: list[str] | None = Query(None),
    session: AsyncSession = Depends(get_session),
    config: Config = Depends(get_config),
) -> TimeSeriesResponse:
    ctx = await _resolve_timeframe(session, from_date, to_date, sprint_id, projects, actors)
    queries = AggregationQueries(session, config)
    result = await queries.collaboration_ts(ctx)
    return TimeSeriesResponse(**result)
