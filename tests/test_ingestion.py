"""Tests for ingestion (EventWriter, cache, bot filter)."""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from project_health.aggregation.cache import AggregationCache
from project_health.db.models import Base, PersonIdentity, RawEvent
from project_health.ingestion.writer import EventWriter
from project_health.providers.protocol import (
    RawChangeRequestEvent,
    RawIssueEvent,
    RawPREvent,
    RawReviewDecisionEvent,
)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_event_writer_dedupe(db_session: AsyncSession):
    writer = EventWriter(db_session)
    events = [
        RawIssueEvent(
            external_id="ISSUE-1",
            timestamp=datetime.now(UTC),
            actor="alice",
            project="PROJ",
            data={"title": "Bug"},
        )
    ]
    count = await writer.write_issues("jira", events)
    assert count == 1

    # Re-insert same external_id should update, not duplicate
    events[0].data["title"] = "Bug Updated"
    count2 = await writer.write_issues("jira", events)
    assert count2 == 1

    result = await db_session.execute(select(RawEvent))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].data["title"] == "Bug Updated"


@pytest.mark.asyncio
async def test_event_writer_allows_same_external_id_across_event_types(db_session: AsyncSession):
    writer = EventWriter(db_session)
    now = datetime.now(UTC)
    await writer.write_pull_requests("launchpad", [
        RawPREvent(
            external_id="mp-1",
            timestamp=now,
            actor="~alice",
            project="repo",
            data={},
        )
    ])
    await writer.write_change_requests("launchpad", [
        RawChangeRequestEvent(
            external_id="mp-1",
            timestamp=now,
            actor="~alice",
            project="repo",
            data={},
        )
    ])

    result = await db_session.execute(select(RawEvent).order_by(RawEvent.event_type))
    rows = result.scalars().all()

    assert [row.event_type for row in rows] == ["change_request", "pull_request"]
    assert {row.id for row in rows} == {
        "launchpad:change_request:mp-1",
        "launchpad:pull_request:mp-1",
    }


@pytest.mark.asyncio
async def test_auto_discovery_unmapped_identity(db_session: AsyncSession):
    writer = EventWriter(db_session)
    events = [
        RawIssueEvent(
            external_id="ISSUE-2",
            timestamp=datetime.now(UTC),
            actor="unknown_user",
            project="PROJ",
            data={},
        )
    ]
    await writer.write_issues("jira", events)

    result = await db_session.execute(
        select(PersonIdentity).where(PersonIdentity.external_id == "unknown_user")
    )
    identity = result.scalar_one_or_none()
    assert identity is not None
    assert identity.person_id is None
    assert identity.source == "jira"


@pytest.mark.asyncio
async def test_auto_discovery_launchpad_identity_details(db_session: AsyncSession):
    writer = EventWriter(db_session)
    await writer.write_issues("launchpad", [
        RawIssueEvent(
            external_id="maas:1",
            timestamp=datetime.now(UTC),
            actor="~alice",
            project="maas",
            data={
                "actor_identity": {
                    "display_name": "Alice Example",
                    "profile_url": "https://launchpad.net/~alice",
                }
            },
        )
    ])

    result = await db_session.execute(
        select(PersonIdentity).where(PersonIdentity.external_id == "~alice")
    )
    identity = result.scalar_one()
    assert identity.display_name == "Alice Example"
    assert identity.profile_url == "https://launchpad.net/~alice"


@pytest.mark.asyncio
async def test_cache_basic():
    c = AggregationCache(ttl_seconds=60)
    c.set("ep", {"a": "1"}, {"github"}, {"commits": 5})
    val = c.get("ep", {"a": "1"}, {"github"})
    assert val == {"commits": 5}
    assert c.hits == 1

    c.invalidate_source("github")
    val2 = c.get("ep", {"a": "1"}, {"github"})
    assert val2 is None
    assert c.misses == 1


def test_bot_filter_from_config():
    from project_health.aggregation.core import get_bot_set
    from project_health.config.loader import Config

    config = Config.model_validate({
        "credentials": {"github_token": "test"},
        "bots": {"github": ["dependabot[bot]"]},
    })
    bots = get_bot_set(config)
    assert "dependabot[bot]" in bots


def test_get_bot_set_uses_passed_config():
    """get_bot_set must accept Config directly, not load via global cache."""
    from project_health.aggregation.core import get_bot_set
    from project_health.config.loader import Config
    config = Config.model_validate({
        "credentials": {"github_token": "test"},
        "bots": {"github": ["my-bot[bot]"]},
    })
    bots = get_bot_set(config)
    assert "my-bot[bot]" in bots


@pytest.mark.asyncio
async def test_event_writer_stores_provider_neutral_events(db_session: AsyncSession):
    writer = EventWriter(db_session)
    now = datetime.now(UTC)

    await writer.write_change_requests("github", [
        RawChangeRequestEvent(
            external_id="42",
            timestamp=now,
            actor="alice",
            project="owner/repo",
            data={"normalized_kind": "change_request", "source_kind": "pull_request"},
        )
    ])
    await writer.write_review_decisions("github", [
        RawReviewDecisionEvent(
            external_id="review-1",
            timestamp=now,
            actor="bob",
            project="owner/repo",
            data={"normalized_kind": "review_decision", "normalized_state": "approved"},
        )
    ])

    result = await db_session.execute(select(RawEvent).order_by(RawEvent.event_type))
    rows = result.scalars().all()

    assert [row.event_type for row in rows] == ["change_request", "review_decision"]
    assert rows[0].data["source_kind"] == "pull_request"
