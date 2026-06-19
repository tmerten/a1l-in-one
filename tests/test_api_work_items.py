"""Integration tests for work-items and commits API endpoints."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from project_health.aggregation.queries import AggregationQueries
from project_health.config.loader import Config
from project_health.db.models import Base, Person, PersonIdentity
from project_health.ingestion.writer import EventWriter
from project_health.providers.protocol import RawCommitEvent, RawIssueEvent, RawPREvent


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def minimal_config():
    return Config.model_validate({"credentials": {"github_token": "test"}})


@pytest.mark.asyncio
async def test_work_items_query_returns_prs_and_issues(db_session: AsyncSession, minimal_config):
    """work_items returns both PRs and issues for a person."""
    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    person = Person(id="p-1", display_name="Alice", active=True)
    db_session.add(person)
    db_session.add(PersonIdentity(person_id="p-1", source="github", external_id="alice"))
    await db_session.commit()

    await writer.write_pull_requests("github", [
        RawPREvent(
            external_id="42",
            timestamp=now,
            actor="alice",
            project="owner/repo",
            data={
                "title": "Fix bug",
                "merged_at": now.isoformat(),
                "additions": 10,
                "deletions": 2,
                "html_url": "https://github.com/owner/repo/pull/42",
            },
        )
    ])

    await writer.write_issues("github", [
        RawIssueEvent(
            external_id="99",
            timestamp=now,
            actor="alice",
            project="owner/repo",
            data={
                "title": "Bug report",
                "state": "closed",
                "html_url": "https://github.com/owner/repo/issues/99",
            },
        )
    ])

    queries = AggregationQueries(db_session, minimal_config)
    items, total = await queries.work_items(
        person_id="p-1",
        status="completed",
        datasource=None,
        event_type=None,
        from_ts=now - timedelta(days=1),
        to_ts=now + timedelta(days=1),
        page=1,
        per_page=20,
    )

    assert total == 2
    assert len(items) == 2
    titles = [i.title for i in items]
    assert "Fix bug" in titles
    assert "Bug report" in titles


@pytest.mark.asyncio
async def test_work_items_query_filters_by_datasource(db_session: AsyncSession, minimal_config):
    """work_items can filter by datasource."""
    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    person = Person(id="p-1", display_name="Alice", active=True)
    db_session.add(person)
    db_session.add(PersonIdentity(person_id="p-1", source="github", external_id="alice"))
    db_session.add(PersonIdentity(person_id="p-1", source="jira", external_id="alice-jira"))
    await db_session.commit()

    await writer.write_pull_requests("github", [
        RawPREvent(
            external_id="42",
            timestamp=now,
            actor="alice",
            project="owner/repo",
            data={"title": "GitHub PR", "merged_at": now.isoformat(), "html_url": "url"},
        )
    ])

    await writer.write_issues("jira", [
        RawIssueEvent(
            external_id="JIRA-1",
            timestamp=now,
            actor="alice-jira",
            project="PROJ",
            data={"summary": "Jira Issue", "status": "Done"},
        )
    ])

    queries = AggregationQueries(db_session, minimal_config)
    items, total = await queries.work_items(
        person_id="p-1",
        status="completed",
        datasource="github",
        event_type=None,
        from_ts=now - timedelta(days=1),
        to_ts=now + timedelta(days=1),
        page=1,
        per_page=20,
    )

    assert total == 1
    assert items[0].datasource == "github"


@pytest.mark.asyncio
async def test_work_items_query_active_returns_open_prs(db_session: AsyncSession, minimal_config):
    """work_items with status=active returns open PRs."""
    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    person = Person(id="p-1", display_name="Alice", active=True)
    db_session.add(person)
    db_session.add(PersonIdentity(person_id="p-1", source="github", external_id="alice"))
    await db_session.commit()

    await writer.write_pull_requests("github", [
        RawPREvent(
            external_id="42",
            timestamp=now,
            actor="alice",
            project="owner/repo",
            data={"title": "Open PR", "state": "open", "html_url": "url"},
        ),
        RawPREvent(
            external_id="43",
            timestamp=now,
            actor="alice",
            project="owner/repo",
            data={"title": "Merged PR", "merged_at": now.isoformat(), "html_url": "url"},
        ),
    ])

    queries = AggregationQueries(db_session, minimal_config)
    items, total = await queries.work_items(
        person_id="p-1",
        status="active",
        datasource=None,
        event_type=None,
        from_ts=None,
        to_ts=None,
        page=1,
        per_page=20,
    )

    assert total == 1
    assert items[0].title == "Open PR"


@pytest.mark.asyncio
async def test_work_items_query_pagination(db_session: AsyncSession, minimal_config):
    """work_items pagination works correctly."""
    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    person = Person(id="p-1", display_name="Alice", active=True)
    db_session.add(person)
    db_session.add(PersonIdentity(person_id="p-1", source="github", external_id="alice"))
    await db_session.commit()

    for i in range(5):
        await writer.write_pull_requests("github", [
            RawPREvent(
                external_id=str(i),
                timestamp=now - timedelta(hours=i),
                actor="alice",
                project="owner/repo",
                data={"title": f"PR {i}", "merged_at": now.isoformat(), "html_url": f"url{i}"},
            )
        ])

    queries = AggregationQueries(db_session, minimal_config)
    page1, total1 = await queries.work_items(
        person_id="p-1",
        status="completed",
        datasource=None,
        event_type=None,
        from_ts=now - timedelta(days=1),
        to_ts=now + timedelta(days=1),
        page=1,
        per_page=2,
    )

    page2, total2 = await queries.work_items(
        person_id="p-1",
        status="completed",
        datasource=None,
        event_type=None,
        from_ts=now - timedelta(days=1),
        to_ts=now + timedelta(days=1),
        page=2,
        per_page=2,
    )

    assert total1 == 5
    assert total2 == 5
    assert len(page1) == 2
    assert len(page2) == 2
    page1_ids = {i.external_id for i in page1}
    page2_ids = {i.external_id for i in page2}
    assert len(page1_ids & page2_ids) == 0


@pytest.mark.asyncio
async def test_commits_query_returns_sha_and_message(db_session: AsyncSession, minimal_config):
    """commits returns commit SHA and message."""
    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    person = Person(id="p-1", display_name="Alice", active=True)
    db_session.add(person)
    db_session.add(PersonIdentity(person_id="p-1", source="github", external_id="alice"))
    await db_session.commit()

    await writer.write_commits("github", [
        RawCommitEvent(
            external_id="abc123def456",
            timestamp=now,
            actor="alice",
            project="owner/repo",
            data={
                "message": "Fix the thing\n\nThis is a longer description.",
                "html_url": "https://github.com/owner/repo/commit/abc123def456",
            },
        )
    ])

    queries = AggregationQueries(db_session, minimal_config)
    items, total = await queries.commits(
        person_id="p-1",
        from_ts=now - timedelta(days=1),
        to_ts=now + timedelta(days=1),
        page=1,
        per_page=20,
    )

    assert total == 1
    assert len(items) == 1
    assert items[0].sha == "abc123d"
    assert "Fix the thing" in items[0].message


@pytest.mark.asyncio
async def test_commits_query_pagination(db_session: AsyncSession, minimal_config):
    """commits pagination works correctly."""
    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    person = Person(id="p-1", display_name="Alice", active=True)
    db_session.add(person)
    db_session.add(PersonIdentity(person_id="p-1", source="github", external_id="alice"))
    await db_session.commit()

    for i in range(5):
        await writer.write_commits("github", [
            RawCommitEvent(
                external_id=f"commit-{i}",
                timestamp=now - timedelta(hours=i),
                actor="alice",
                project="owner/repo",
                data={"message": f"Commit {i}", "html_url": f"url-{i}"},
            )
        ])

    queries = AggregationQueries(db_session, minimal_config)
    page1, total1 = await queries.commits(
        person_id="p-1",
        from_ts=now - timedelta(days=1),
        to_ts=now + timedelta(days=1),
        page=1,
        per_page=2,
    )

    page2, total2 = await queries.commits(
        person_id="p-1",
        from_ts=now - timedelta(days=1),
        to_ts=now + timedelta(days=1),
        page=2,
        per_page=2,
    )

    assert total1 == 5
    assert total2 == 5
    assert len(page1) == 2
    assert len(page2) == 2
    page1_ids = {i.id for i in page1}
    page2_ids = {i.id for i in page2}
    assert len(page1_ids & page2_ids) == 0


@pytest.mark.asyncio
async def test_work_items_unknown_person_returns_empty(db_session: AsyncSession, minimal_config):
    """work_items returns empty for unknown person."""
    queries = AggregationQueries(db_session, minimal_config)
    items, total = await queries.work_items(
        person_id="unknown",
        status="completed",
        datasource=None,
        event_type=None,
        from_ts=datetime.now(timezone.utc) - timedelta(days=1),
        to_ts=datetime.now(timezone.utc) + timedelta(days=1),
        page=1,
        per_page=20,
    )

    assert items == []
    assert total == 0


@pytest.mark.asyncio
async def test_work_items_extracts_jira_metadata(db_session: AsyncSession, minimal_config):
    """work_items extracts Jira-specific metadata like story points."""
    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    person = Person(id="p-1", display_name="Alice", active=True)
    db_session.add(person)
    db_session.add(PersonIdentity(person_id="p-1", source="jira", external_id="alice-jira"))
    await db_session.commit()

    await writer.write_issues("jira", [
        RawIssueEvent(
            external_id="PROJ-123",
            timestamp=now,
            actor="alice-jira",
            project="PROJ",
            data={
                "summary": "Implement feature",
                "description": "As a user...",
                "status": "Done",
                "issue_type": "Feature",
                "story_points": 5,
                "labels": ["auth", "security"],
            },
        )
    ])

    queries = AggregationQueries(db_session, minimal_config)
    items, _ = await queries.work_items(
        person_id="p-1",
        status="completed",
        datasource="jira",
        event_type=None,
        from_ts=now - timedelta(days=1),
        to_ts=now + timedelta(days=1),
        page=1,
        per_page=20,
    )

    assert len(items) == 1
    item = items[0]
    assert item.title == "Implement feature"
    assert item.status == "Done"
    assert item.metadata is not None
    assert item.metadata.issue_type == "Feature"
    assert item.metadata.story_points == 5
    assert item.metadata.labels == ["auth", "security"]
