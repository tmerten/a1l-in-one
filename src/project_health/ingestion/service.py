"""Shared orchestration for scheduled, manual, and backfill ingestion."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from project_health.db.models import IngestionRun
from project_health.db.session import get_session_maker
from project_health.ingestion.events import EVENT_DEFINITIONS
from project_health.ingestion.scheduler import IngestionRunner
from project_health.providers.protocol import DataSourceProvider, EventType


class UnsupportedEventTypeError(ValueError):
    """Raised when a provider does not support a requested event type."""


class IngestionService:
    """Select and execute capability-aware ingestion targets."""

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._session_maker = session_maker or get_session_maker()

    def event_types_for(
        self,
        provider: DataSourceProvider,
        requested: str | EventType | None = None,
    ) -> tuple[EventType, ...]:
        if requested is not None:
            try:
                event_type = EventType(requested)
            except ValueError as exc:
                raise UnsupportedEventTypeError(
                    f"Unknown event type '{requested}'"
                ) from exc
            if event_type not in provider.capabilities:
                raise UnsupportedEventTypeError(
                    f"Provider '{provider.id}' does not support event type '{event_type.value}'"
                )
            return (event_type,)

        return tuple(
            definition.event_type
            for definition in EVENT_DEFINITIONS
            if definition.event_type in provider.capabilities
        )

    def targets_for(
        self,
        providers: list[DataSourceProvider],
        requested: str | EventType | None = None,
        *,
        reject_unsupported: bool = False,
    ) -> tuple[tuple[DataSourceProvider, EventType], ...]:
        if requested is None:
            return tuple(
                (provider, event_type)
                for provider in providers
                for event_type in self.event_types_for(provider)
            )

        try:
            event_type = EventType(requested)
        except ValueError as exc:
            raise UnsupportedEventTypeError(
                f"Unknown event type '{requested}'"
            ) from exc

        targets = tuple(
            (provider, event_type)
            for provider in providers
            if event_type in provider.capabilities
        )
        if reject_unsupported and len(targets) != len(providers):
            unsupported = next(
                provider for provider in providers if event_type not in provider.capabilities
            )
            raise UnsupportedEventTypeError(
                f"Provider '{unsupported.id}' does not support event type '{event_type.value}'"
            )
        return targets

    async def run_target(
        self,
        provider: DataSourceProvider,
        event_type: str | EventType,
        trigger: str,
        force_since: datetime | None = None,
    ) -> IngestionRun:
        selected = self.event_types_for(provider, event_type)
        async with self._session_maker() as session:
            runner = IngestionRunner(session)
            return await runner.run(
                provider,
                selected[0],
                trigger=trigger,
                force_since=force_since,
            )

    async def run_provider(
        self,
        provider: DataSourceProvider,
        trigger: str,
        event_type: str | EventType | None = None,
        force_since: datetime | None = None,
    ) -> list[IngestionRun]:
        results = []
        for selected in self.event_types_for(provider, event_type):
            results.append(
                await self.run_target(
                    provider,
                    selected,
                    trigger=trigger,
                    force_since=force_since,
                )
            )
        return results
