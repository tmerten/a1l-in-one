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
from project_health.providers.protocol import RawIssueEvent


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


def test_bot_filter_from_config(monkeypatch):
    import project_health.aggregation.core as core_mod
    from project_health.config.loader import Config

    # Reset cache
    core_mod.BOT_CACHE = None

    # Mock load_config inside core_mod (where it's imported)
    orig_load = core_mod.load_config
    def mock_load(_path=None):
        return Config.model_validate({
            "credentials": {"github_token": "test"},
            "bots": {"github": ["dependabot[bot]"]}
        })
    core_mod.load_config = mock_load
    try:
        bots = core_mod.get_bot_set()
        assert "dependabot[bot]" in bots
    finally:
        core_mod.load_config = orig_load
        core_mod.BOT_CACHE = None
