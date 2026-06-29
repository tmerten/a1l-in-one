"""EventWriter — upserts raw events into the database."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from project_health.db.models import PersonIdentity, RawEvent
from project_health.providers.protocol import (
    RawChangeRequestEvent,
    RawCommitEvent,
    RawIssueEvent,
    RawPREvent,
    RawReviewCommentEvent,
    RawReviewDecisionEvent,
    RawReviewEvent,
    RawReviewRequestEvent,
)


class EventWriter:
    """Writes raw events to the database with deduplication."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write_commits(
        self, source: str, events: list[RawCommitEvent]
    ) -> int:
        return await self._upsert_events(source, "commit", events)

    async def write_pull_requests(
        self, source: str, events: list[RawPREvent]
    ) -> int:
        return await self._upsert_events(source, "pull_request", events)

    async def write_change_requests(
        self, source: str, events: list[RawChangeRequestEvent]
    ) -> int:
        return await self._upsert_events(source, "change_request", events)

    async def write_pull_request_reviews(
        self, source: str, events: list[RawReviewEvent]
    ) -> int:
        return await self._upsert_events(source, "pull_request_review", events)

    async def write_review_requests(
        self, source: str, events: list[RawReviewRequestEvent]
    ) -> int:
        return await self._upsert_events(source, "review_request", events)

    async def write_review_decisions(
        self, source: str, events: list[RawReviewDecisionEvent]
    ) -> int:
        return await self._upsert_events(source, "review_decision", events)

    async def write_review_comments(
        self, source: str, events: list[RawReviewCommentEvent]
    ) -> int:
        return await self._upsert_events(source, "review_comment", events)

    async def write_issues(
        self, source: str, events: list[RawIssueEvent]
    ) -> int:
        return await self._upsert_events(source, "issue", events)

    async def _upsert_events(
        self,
        source: str,
        event_type: str,
        events: Sequence[
            RawCommitEvent
            | RawPREvent
            | RawChangeRequestEvent
            | RawReviewEvent
            | RawReviewRequestEvent
            | RawReviewDecisionEvent
            | RawReviewCommentEvent
            | RawIssueEvent
        ],
    ) -> int:
        """Upsert events keyed on (source, event_type, external_id).

        Also auto-discovers new (source, actor) identities as unmapped placeholders.
        Returns the number of events written.
        """
        if not events:
            return 0

        now = datetime.now(UTC)
        written = 0

        for ev in events:
            # Auto-discovery: ensure person_identities placeholder for new actors
            if ev.actor:
                await self._ensure_identity_placeholder(source, ev.actor, ev.data)

            # Build upsert via SQLite ON CONFLICT (simpler than dialect-specific)
            stmt = (
                insert(RawEvent)
                .values(
                    id=_raw_event_id(source, event_type, ev.external_id),
                    source=source,
                    event_type=event_type,
                    external_id=ev.external_id,
                    timestamp=ev.timestamp,
                    ingested_at=now,
                    actor=ev.actor,
                    project=ev.project,
                    data=ev.data,
                )
                .on_conflict_do_update(
                    index_elements=["source", "event_type", "external_id"],
                    set_={
                        "timestamp": ev.timestamp,
                        "ingested_at": now,
                        "actor": ev.actor,
                        "project": ev.project,
                        "data": ev.data,
                    },
                )
            )
            await self._session.execute(stmt)
            written += 1

        await self._session.commit()
        return written

    async def _ensure_identity_placeholder(
        self,
        source: str,
        external_id: str,
        data: dict,
    ) -> None:
        """Insert a person_identities row with person_id=NULL if not exists."""
        display_name, profile_url, details = _identity_details(source, external_id, data)
        result = await self._session.execute(
            select(PersonIdentity).where(
                PersonIdentity.source == source,
                PersonIdentity.external_id == external_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            placeholder = PersonIdentity(
                person_id=None,
                source=source,
                external_id=external_id,
                display_name=display_name,
                profile_url=profile_url,
                data=details,
            )
            self._session.add(placeholder)
            await self._session.flush()
        else:
            if display_name and not existing.display_name:
                existing.display_name = display_name
            if profile_url and not existing.profile_url:
                existing.profile_url = profile_url
            if details and not existing.data:
                existing.data = details


def _identity_details(source: str, external_id: str, data: dict) -> tuple[str | None, str | None, dict]:
    identity = data.get("actor_identity")
    if isinstance(identity, dict):
        display_name = identity.get("display_name")
        profile_url = identity.get("profile_url") or identity.get("web_link")
        return (
            str(display_name) if display_name else None,
            str(profile_url) if profile_url else None,
            identity,
        )
    if source == "launchpad":
        return None, f"https://launchpad.net/{external_id}", {}
    return None, None, {}


def _raw_event_id(source: str, event_type: str, external_id: str) -> str:
    return f"{source}:{event_type}:{external_id}"
