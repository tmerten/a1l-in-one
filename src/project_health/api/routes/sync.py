"""Sync API endpoints: manual trigger and status."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from project_health.aggregation.cache import cache
from project_health.api.deps import get_config
from project_health.config.loader import Config
from project_health.db.models import IngestionRun
from project_health.db.session import get_session_maker
from project_health.ingestion.scheduler import IngestionRunner
from project_health.providers.registry import build_registry

router = APIRouter()


class SyncRunResponse(BaseModel):
    run_id: str
    source: str
    event_type: str
    status: str


class SyncStatusItem(BaseModel):
    source: str
    target: str | None = None
    target_type: str | None = None
    last_success_at: datetime | None
    last_status: str
    events_count: int | None


class SyncStatusResponse(BaseModel):
    sources: list[SyncStatusItem]
    cache_hits: int = 0
    cache_misses: int = 0
    any_running: bool = False


@router.post("/run", status_code=202)
async def sync_run(
    source: str | None = Query(None),
    event_type: str | None = Query(None),
    config: Config = Depends(get_config),
) -> list[SyncRunResponse]:
    """Trigger an immediate ingestion run for all providers (or a specific one)."""
    registry = await build_registry(config)

    event_types = [
        "commit",
        "pull_request",
        "change_request",
        "pull_request_review",
        "review_request",
        "review_decision",
        "review_comment",
        "issue",
        "sprint",
    ]
    targets: list[tuple] = []
    if source:
        provider = registry.get(source)
        if provider is None:
            raise HTTPException(status_code=404, detail=f"Source '{source}' not found")
        targets.append((provider, event_type or "issue"))
    else:
        for prov in registry.all():
            for et in event_types:
                targets.append((prov, et))

    responses: list[SyncRunResponse] = []
    maker = get_session_maker()

    for prov, et in targets:
        async with maker() as session:
            inflight = await session.execute(
                select(IngestionRun)
                .where(
                    IngestionRun.source == prov.id,
                    IngestionRun.status == "running",
                )
                .limit(1)
            )
            existing = inflight.scalar_one_or_none()
            if existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": f"Provider {prov.id} is busy",
                        "run_id": existing.id,
                    },
                )
            runner = IngestionRunner(session)
            result = await runner.run(prov, et, trigger="manual")
            responses.append(
                SyncRunResponse(
                    run_id=result.id,
                    source=prov.id,
                    event_type=et,
                    status=result.status,
                )
            )

    return responses


@router.get("/status")
async def sync_status() -> SyncStatusResponse:
    """Get per-source freshness and cache metrics."""
    maker = get_session_maker()
    sources: list[SyncStatusItem] = []
    async with maker() as session:
        result = await session.execute(
            select(
                IngestionRun.source,
                func.max(IngestionRun.started_at).label("last_started"),
            )
            .where(IngestionRun.status == "success")
            .group_by(IngestionRun.source)
        )
        rows = result.all()
        for row in rows:
            status_result = await session.execute(
                select(IngestionRun)
                .where(
                    IngestionRun.source == row.source,
                    IngestionRun.started_at == row.last_started,
                )
                .order_by(IngestionRun.started_at.desc())
                .limit(1)
            )
            run = status_result.scalar_one()
            sources.append(
                SyncStatusItem(
                    source=row.source,
                    target=None,
                    target_type=None,
                    last_success_at=run.finished_at,
                    last_status=run.status,
                    events_count=run.events_count,
                )
            )
        running_result = await session.execute(
            select(IngestionRun.source)
            .where(IngestionRun.status == "running")
            .limit(1)
        )
        any_running = running_result.scalar_one_or_none() is not None
    stats = cache.stats()
    return SyncStatusResponse(
        sources=sources,
        cache_hits=stats["hits"],
        cache_misses=stats["misses"],
        any_running=any_running,
    )
