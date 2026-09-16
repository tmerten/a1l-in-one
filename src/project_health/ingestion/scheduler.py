"""In-process scheduler and ingestion runner."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_health.config.loader import Config
from project_health.db.models import IngestionRun
from project_health.db.session import get_session_maker
from project_health.ingestion.events import EVENT_REGISTRY
from project_health.ingestion.writer import EventWriter
from project_health.providers.protocol import DataSourceProvider, EventType
from project_health.providers.registry import DataSourceRegistry

logger = logging.getLogger(__name__)


class IngestionRunner:
    """Runs a single ingestion job: creates record, fetches, writes, updates record."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._writer = EventWriter(session)

    async def run(
        self,
        provider: DataSourceProvider,
        event_type: EventType,
        trigger: str,
        force_since: datetime | None = None,
    ) -> IngestionRun:
        """Run ingestion for a single (provider, event_type) pair.

        Args:
            provider: The data source provider instance.
            event_type: Provider event type such as commit, change_request, review_decision, issue, sprint.
            trigger: scheduled | manual | backfill
            force_since: Override the since parameter (used by backfill).
        """
        source = provider.id
        run = IngestionRun(
            source=source,
            event_type=event_type,
            started_at=datetime.now(UTC),
            status="running",
            trigger=trigger,
        )
        self._session.add(run)
        await self._session.commit()
        await self._session.refresh(run)

        since: datetime
        if force_since is not None:
            since = force_since
        else:
            since = await self._derive_since(source, event_type)

        # SQLite may return naive datetimes; ensure UTC for provider comparisons
        if since.tzinfo is None:
            since = since.replace(tzinfo=UTC)

        try:
            definition = EVENT_REGISTRY[event_type]
            events = await self._fetch_with_retry(provider, definition.fetch, since)
            count = await definition.write(self._writer, source, events)
            run.status = "success"
            run.events_count = count
        except Exception as exc:
            logger.exception("Ingestion failed for %s/%s", source, event_type)
            run.status = "failure"
            run.error_message = str(exc)
        finally:
            run.finished_at = datetime.now(UTC)
            await self._session.commit()

        return run

    async def _derive_since(self, source: str, event_type: EventType) -> datetime:
        """Derive `since` from the most recent successful run."""
        result = await self._session.execute(
            select(IngestionRun)
            .where(
                IngestionRun.source == source,
                IngestionRun.event_type == event_type,
                IngestionRun.status == "success",
            )
            .order_by(IngestionRun.started_at.desc())
            .limit(1)
        )
        last_run = result.scalar_one_or_none()
        if last_run is None:
            # No prior successful run — default to 90 days to capture meaningful history
            return datetime.now(UTC) - timedelta(days=90)
        return last_run.started_at

    async def _fetch_with_retry(
        self,
        provider: DataSourceProvider,
        fetch: Callable[[DataSourceProvider, datetime], Awaitable[list[Any]]],
        since: datetime,
    ) -> list[Any]:
        """Fetch events with exponential backoff on transient failures."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await fetch(provider, since)
            except RuntimeError as exc:
                # Auth errors are RuntimeError from providers — fail fast
                if "auth error" in str(exc).lower() or str(exc).startswith("GitHub auth"):
                    raise
                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    logger.warning(
                        "Transient error fetching %s/%s (attempt %d/%d), retrying in %ds: %s",
                        provider.id,
                        fetch.__name__,
                        attempt + 1,
                        max_retries,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
        raise RuntimeError("Ingestion fetch retry loop exited unexpectedly")


class SchedulerManager:
    """Manages APScheduler jobs for ingestion."""

    def __init__(self, config: Config, registry: DataSourceRegistry) -> None:
        self._config = config
        self._registry = registry
        self._scheduler: AsyncIOScheduler | None = None
        self._locks: dict[str, asyncio.Lock] = {}

    def start(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._scheduler.start()

        interval = max(self._config.ingestion.interval_minutes, 1)
        from project_health.ingestion.service import IngestionService

        service = IngestionService()
        for provider, event_type in service.targets_for(self._registry.all()):
            lock_key = f"{provider.id}:{event_type}"
            self._locks[lock_key] = asyncio.Lock()
            job_id = f"{provider.id}:{event_type}"
            self._scheduler.add_job(
                self._run_job,
                "interval",
                minutes=interval,
                id=job_id,
                replace_existing=True,
                args=[provider, event_type],
            )
            logger.info("Scheduled job %s every %d minutes", job_id, interval)

    def shutdown(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=False)

    async def _run_job(self, provider: DataSourceProvider, event_type: EventType) -> None:
        lock_key = f"{provider.id}:{event_type}"
        lock = self._locks.get(lock_key)
        if lock is None:
            return

        if lock.locked():
            logger.info("Skipping %s/%s — previous run still in flight", provider.id, event_type)
            # Write a skipped ingestion run record
            maker = get_session_maker()
            async with maker() as session:
                run = IngestionRun(
                    source=provider.id,
                    event_type=event_type,
                    started_at=datetime.now(UTC),
                    finished_at=datetime.now(UTC),
                    status="skipped",
                    trigger="scheduled",
                )
                session.add(run)
                await session.commit()
            return

        async with lock:
            from project_health.ingestion.service import IngestionService

            try:
                result = await IngestionService().run_target(
                    provider, event_type, trigger="scheduled"
                )
                if result.status == "success":
                    logger.info(
                        "Ingestion success %s/%s: %d events",
                        provider.id,
                        event_type,
                        result.events_count or 0,
                    )
                elif result.status == "failure":
                    logger.error(
                        "Ingestion failure %s/%s: %s",
                        provider.id,
                        event_type,
                        result.error_message,
                    )
            except Exception:
                logger.exception("Unhandled error in ingestion job %s/%s", provider.id, event_type)
