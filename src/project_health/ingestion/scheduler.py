"""In-process scheduler and ingestion runner."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from project_health.config.loader import Config
from project_health.db.models import IngestionRun
from project_health.db.session import get_session_maker
from project_health.ingestion.writer import EventWriter
from project_health.providers.protocol import DataSourceProvider

logger = logging.getLogger(__name__)


class IngestionRunner:
    """Runs a single ingestion job: creates record, fetches, writes, updates record."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._writer = EventWriter(session)

    async def run(
        self,
        provider: DataSourceProvider,
        event_type: str,
        trigger: str,
        force_since: datetime | None = None,
    ) -> IngestionRun:
        """Run ingestion for a single (provider, event_type) pair.

        Args:
            provider: The data source provider instance.
            event_type: One of commit, pull_request, pull_request_review, issue, sprint.
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

        try:
            events = await self._fetch_with_retry(provider, event_type, since)
            count = await self._write_events(source, event_type, events)
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

    async def _derive_since(self, source: str, event_type: str) -> datetime:
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
            # No prior successful run — default to 1 day to avoid massive backfill on first tick
            return datetime.now(UTC) - timedelta(days=1)
        return last_run.started_at

    async def _fetch_with_retry(
        self,
        provider: DataSourceProvider,
        event_type: str,
        since: datetime,
    ) -> list:
        """Fetch events with exponential backoff on transient failures."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if event_type == "commit":
                    return await provider.fetch_commits(since)
                if event_type == "pull_request":
                    return await provider.fetch_pull_requests(since)
                if event_type == "pull_request_review":
                    return await provider.fetch_pull_request_reviews(since)
                if event_type == "issue":
                    return await provider.fetch_issues(since)
                if event_type == "sprint":
                    return await provider.fetch_sprints()
                return []
            except RuntimeError as exc:
                # Auth errors are RuntimeError from providers — fail fast
                if "auth error" in str(exc).lower() or str(exc).startswith("GitHub auth"):
                    raise
                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    logger.warning(
                        "Transient error fetching %s/%s (attempt %d/%d), retrying in %ds: %s",
                        provider.id,
                        event_type,
                        attempt + 1,
                        max_retries,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
        return []

    async def _write_events(
        self, source: str, event_type: str, events: list
    ) -> int:
        if event_type == "commit":
            return await self._writer.write_commits(source, events)
        if event_type == "pull_request":
            return await self._writer.write_pull_requests(source, events)
        if event_type == "pull_request_review":
            return await self._writer.write_pull_request_reviews(source, events)
        if event_type == "issue":
            return await self._writer.write_issues(source, events)
        if event_type == "sprint":
            # Sprint definitions are written to sprints table via dedicated method
            from project_health.db.models import Sprint
            count = 0
            for sp in events:
                await self._session.merge(
                    Sprint(
                        id=sp.id,
                        name=sp.name,
                        project=sp.project,
                        start_date=sp.start_date,
                        end_date=sp.end_date,
                        state=sp.state,
                    )
                )
                count += 1
            await self._session.commit()
            return count
        return 0


class SchedulerManager:
    """Manages APScheduler jobs for ingestion."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._scheduler: AsyncIOScheduler | None = None
        self._locks: dict[str, asyncio.Lock] = {}

    def start(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._scheduler.start()

        # Register one job per (provider, event_type)
        event_types = [
            "commit",
            "pull_request",
            "pull_request_review",
            "issue",
            "sprint",
        ]
        interval = max(self._config.ingestion.interval_minutes, 1)

        # Build providers list
        providers: list[DataSourceProvider] = []
        if self._config.projects.github:
            from project_health.providers.github import GitHubProvider
            providers.append(GitHubProvider(self._config))
        if self._config.projects.jira:
            from project_health.providers.jira import JiraProvider
            providers.append(JiraProvider(self._config))

        for provider in providers:
            self._locks[provider.id] = asyncio.Lock()
            for et in event_types:
                job_id = f"{provider.id}:{et}"
                self._scheduler.add_job(
                    self._run_job,
                    "interval",
                    minutes=interval,
                    id=job_id,
                    replace_existing=True,
                    args=[provider, et],
                )
                logger.info("Scheduled job %s every %d minutes", job_id, interval)

    def shutdown(self) -> None:
        if self._scheduler:
            self._scheduler.shutdown(wait=False)

    async def _run_job(self, provider: DataSourceProvider, event_type: str) -> None:
        lock = self._locks.get(provider.id)
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
            maker = get_session_maker()
            async with maker() as session:
                runner = IngestionRunner(session)
                try:
                    result = await runner.run(provider, event_type, trigger="scheduled")
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
