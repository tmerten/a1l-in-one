"""Typed ingestion event registry and dispatch functions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from project_health.ingestion.writer import EventWriter
from project_health.providers.protocol import DataSourceProvider, EventType

FetchEvents = Callable[[DataSourceProvider, datetime], Awaitable[list[Any]]]
WriteEvents = Callable[[EventWriter, str, list[Any]], Awaitable[int]]


@dataclass(frozen=True)
class EventDefinition:
    event_type: EventType
    fetch: FetchEvents
    write: WriteEvents


async def _fetch_commits(provider: DataSourceProvider, since: datetime) -> list[Any]:
    return await provider.fetch_commits(since)


async def _fetch_pull_requests(provider: DataSourceProvider, since: datetime) -> list[Any]:
    return await provider.fetch_pull_requests(since)


async def _fetch_change_requests(provider: DataSourceProvider, since: datetime) -> list[Any]:
    return await provider.fetch_change_requests(since)


async def _fetch_pull_request_reviews(
    provider: DataSourceProvider, since: datetime
) -> list[Any]:
    return await provider.fetch_pull_request_reviews(since)


async def _fetch_review_requests(provider: DataSourceProvider, since: datetime) -> list[Any]:
    return await provider.fetch_review_requests(since)


async def _fetch_review_decisions(provider: DataSourceProvider, since: datetime) -> list[Any]:
    return await provider.fetch_review_decisions(since)


async def _fetch_review_comments(provider: DataSourceProvider, since: datetime) -> list[Any]:
    return await provider.fetch_review_comments(since)


async def _fetch_issues(provider: DataSourceProvider, since: datetime) -> list[Any]:
    return await provider.fetch_issues(since)


async def _fetch_sprints(provider: DataSourceProvider, _since: datetime) -> list[Any]:
    return await provider.fetch_sprints()


async def _write_commits(writer: EventWriter, source: str, events: list[Any]) -> int:
    return await writer.write_commits(source, events)


async def _write_pull_requests(writer: EventWriter, source: str, events: list[Any]) -> int:
    return await writer.write_pull_requests(source, events)


async def _write_change_requests(writer: EventWriter, source: str, events: list[Any]) -> int:
    return await writer.write_change_requests(source, events)


async def _write_pull_request_reviews(
    writer: EventWriter, source: str, events: list[Any]
) -> int:
    return await writer.write_pull_request_reviews(source, events)


async def _write_review_requests(writer: EventWriter, source: str, events: list[Any]) -> int:
    return await writer.write_review_requests(source, events)


async def _write_review_decisions(writer: EventWriter, source: str, events: list[Any]) -> int:
    return await writer.write_review_decisions(source, events)


async def _write_review_comments(writer: EventWriter, source: str, events: list[Any]) -> int:
    return await writer.write_review_comments(source, events)


async def _write_issues(writer: EventWriter, source: str, events: list[Any]) -> int:
    return await writer.write_issues(source, events)


async def _write_sprints(writer: EventWriter, source: str, events: list[Any]) -> int:
    return await writer.write_sprints(source, events)


EVENT_DEFINITIONS = (
    EventDefinition(EventType.COMMIT, _fetch_commits, _write_commits),
    EventDefinition(EventType.PULL_REQUEST, _fetch_pull_requests, _write_pull_requests),
    EventDefinition(EventType.CHANGE_REQUEST, _fetch_change_requests, _write_change_requests),
    EventDefinition(
        EventType.PULL_REQUEST_REVIEW,
        _fetch_pull_request_reviews,
        _write_pull_request_reviews,
    ),
    EventDefinition(EventType.REVIEW_REQUEST, _fetch_review_requests, _write_review_requests),
    EventDefinition(EventType.REVIEW_DECISION, _fetch_review_decisions, _write_review_decisions),
    EventDefinition(EventType.REVIEW_COMMENT, _fetch_review_comments, _write_review_comments),
    EventDefinition(EventType.ISSUE, _fetch_issues, _write_issues),
    EventDefinition(EventType.SPRINT, _fetch_sprints, _write_sprints),
)

EVENT_REGISTRY = {definition.event_type: definition for definition in EVENT_DEFINITIONS}
