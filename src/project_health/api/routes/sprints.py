"""Sprints API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

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
) -> list[SprintResponse]:
    """List sprints for a project. Returns active + completed from last 90 days."""
    maker = get_session()
    async with maker() as session:
        stmt = select(Sprint).order_by(Sprint.end_date.desc())
        if project:
            stmt = stmt.where(Sprint.project == project)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        cutoff = datetime.now(UTC) - timedelta(days=90)
        active_states = {"active", "future"}
        filtered = [
            row for row in rows
            if row.state in active_states or row.end_date >= cutoff
        ]

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
            for row in filtered
        ]
