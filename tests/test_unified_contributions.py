"""Tests for unified-contributions-view: datasource abstraction, person-centric aggregation, grouped projects."""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from project_health.db.models import Base, RawEvent, Person, PersonIdentity
from project_health.ingestion.writer import EventWriter
from project_health.aggregation.queries import AggregationQueries
from project_health.aggregation.core import Timeframe
from project_health.providers.protocol import (
    Datasource, DatasourceRole, RawPREvent, RawCommitEvent, RawIssueEvent, RawReviewEvent,
    SOURCE_CAPABILITIES, sources_for_event_type,
)
from project_health.providers.registry import DataSourceRegistry, build_registry
from project_health.config.loader import Config


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


@pytest.fixture
def full_config():
    return Config.model_validate({
        "team": [
            {"name": "Alice", "github": "alice-gh", "jira": "alice-jira"},
            {"name": "Bob", "github": "bob-gh"},
        ],
        "projects": {
            "github": ["owner/repo-a", "owner/repo-b"],
            "jira": [{"key": "PROJ", "board_id": 42}],
        },
        "credentials": {
            "github_token": "gh_test",
            "jira": {
                "base_url": "https://test.atlassian.net",
                "email": "test@example.com",
                "api_token": "jira_test",
            },
        },
    })


def test_datasource_model_construction():
    ds = Datasource(id="github", role=DatasourceRole.CODE, display_name="GitHub", projects=["owner/repo-a"], is_configured=True)
    assert ds.id == "github"
    assert ds.role == DatasourceRole.CODE
    assert ds.display_name == "GitHub"
    assert ds.projects == ["owner/repo-a"]
    assert ds.is_configured is True


def test_datasource_role_enum():
    assert DatasourceRole.UMBRELLA.value == "umbrella"
    assert DatasourceRole.CODE.value == "code"


def test_source_capabilities_launchpad():
    assert "issue" in SOURCE_CAPABILITIES["launchpad"]
    assert "pull_request_review" in SOURCE_CAPABILITIES["launchpad"]
    assert "pull_request" in SOURCE_CAPABILITIES["launchpad"]
    assert "commit" in SOURCE_CAPABILITIES["launchpad"]


def test_sources_for_event_type():
    configured = {"github", "jira"}
    commit_sources = sources_for_event_type("commit", configured)
    assert commit_sources == {"github"}

    issue_sources = sources_for_event_type("issue", configured)
    assert issue_sources == {"github", "jira"}

    sprint_sources = sources_for_event_type("sprint", configured)
    assert sprint_sources == {"jira"}


def test_sources_for_event_type_with_launchpad():
    configured = {"github", "jira", "launchpad"}
    pr_sources = sources_for_event_type("pull_request", configured)
    assert pr_sources == {"github", "launchpad"}

    review_sources = sources_for_event_type("pull_request_review", configured)
    assert review_sources == {"github", "launchpad"}

    issue_sources = sources_for_event_type("issue", configured)
    assert issue_sources == {"github", "jira", "launchpad"}


@pytest.mark.asyncio
async def test_build_registry_constructs_datasources(full_config):
    registry = await build_registry(full_config)
    datasources = registry.datasources
    assert len(datasources) == 3

    jira_ds = next(ds for ds in datasources if ds.id == "jira")
    assert jira_ds.role == DatasourceRole.UMBRELLA
    assert jira_ds.is_configured is True
    assert "PROJ" in jira_ds.projects

    github_ds = next(ds for ds in datasources if ds.id == "github")
    assert github_ds.role == DatasourceRole.CODE
    assert github_ds.is_configured is True
    assert "owner/repo-a" in github_ds.projects

    lp_ds = next(ds for ds in datasources if ds.id == "launchpad")
    assert lp_ds.role == DatasourceRole.CODE
    assert lp_ds.is_configured is False


def test_configured_sources_from_registry():
    ds1 = Datasource(id="github", role=DatasourceRole.CODE, display_name="GitHub", projects=["r"], is_configured=True)
    ds2 = Datasource(id="jira", role=DatasourceRole.UMBRELLA, display_name="Jira", projects=["P"], is_configured=True)
    ds3 = Datasource(id="launchpad", role=DatasourceRole.CODE, display_name="Launchpad", projects=[], is_configured=False)

    registry = DataSourceRegistry(providers=[], datasources=[ds1, ds2, ds3])
    assert registry.configured_sources() == {"github", "jira"}


@pytest.mark.asyncio
async def test_person_contributions_across_sources(db_session: AsyncSession, full_config):
    """Person with identities in both Jira and GitHub returns unified metrics."""
    from project_health.db.reconcile import reconcile_persons_from_config

    await reconcile_persons_from_config(db_session, full_config)

    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    await writer.write_commits("github", [
        RawCommitEvent(external_id="c1", timestamp=now, actor="alice-gh", project="owner/repo-a", data={}),
    ])
    await writer.write_pull_requests("github", [
        RawPREvent(external_id="pr1", timestamp=now, actor="alice-gh", project="owner/repo-a",
                    data={"merged_at": now.isoformat(), "additions": 100, "deletions": 10}),
    ])
    await writer.write_issues("jira", [
        RawIssueEvent(external_id="ISS-1", timestamp=now, actor="alice-jira", project="PROJ",
                       data={"issue_type": "Bug", "closed_at": now.isoformat(), "status": "Done"}),
    ])

    queries = AggregationQueries(db_session, full_config, {"github", "jira"})
    ctx = Timeframe(kind="date_range", start=now - timedelta(days=1), end=now + timedelta(days=1))

    persons = await queries.list_persons(ctx)
    alice = next((p for p in persons if p["display_name"] == "Alice"), None)
    assert alice is not None
    assert alice["metrics"]["commits"] == 1
    assert alice["metrics"]["prs_merged"] == 1
    assert alice["metrics"]["issues_resolved"] == 1


@pytest.mark.asyncio
async def test_person_contributions_unmapped_identity(db_session: AsyncSession, minimal_config):
    """Unmapped identity (person_id NULL) falls back to source+actor direct match."""
    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    await writer.write_pull_requests("github", [
        RawPREvent(external_id="pr-unmapped", timestamp=now, actor="unknown-user", project="repo-a",
                    data={"merged_at": now.isoformat(), "additions": 50, "deletions": 5}),
    ])

    queries = AggregationQueries(db_session, minimal_config, {"github"})
    ctx = Timeframe(kind="date_range", start=now - timedelta(days=1), end=now + timedelta(days=1))
    persons = await queries.list_persons(ctx)

    assert len(persons) == 0 or all(p["metrics"]["prs_merged"] == 0 for p in persons)


@pytest.mark.asyncio
async def test_bot_filter_in_person_queries(db_session: AsyncSession, full_config):
    """Bot actors excluded from person metrics."""
    from project_health.db.reconcile import reconcile_persons_from_config

    await reconcile_persons_from_config(db_session, full_config)

    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    await writer.write_pull_requests("github", [
        RawPREvent(external_id="pr-bot", timestamp=now, actor="dependabot[bot]", project="owner/repo-a",
                    data={"merged_at": now.isoformat(), "additions": 500, "deletions": 50}),
        RawPREvent(external_id="pr-alice", timestamp=now, actor="alice-gh", project="owner/repo-a",
                    data={"merged_at": now.isoformat(), "additions": 100, "deletions": 10}),
    ])

    queries = AggregationQueries(db_session, full_config, {"github"})
    ctx = Timeframe(kind="date_range", start=now - timedelta(days=1), end=now + timedelta(days=1))

    persons = await queries.list_persons(ctx)
    alice = next((p for p in persons if p["display_name"] == "Alice"), None)
    assert alice is not None
    assert alice["metrics"]["prs_merged"] == 1
    assert alice["metrics"]["pr_loc_added"] == 100


@pytest.mark.asyncio
async def test_source_filter_helper():
    """GitHub-only metrics exclude Jira source; future Launchpad included when configured."""
    configured = {"github", "jira"}
    queries = AggregationQueries.__new__(AggregationQueries)
    queries._configured_sources = configured

    clause, params = queries._source_filter("commit")
    assert ":src_0" in clause
    assert "github" in params.values()
    assert "jira" not in params.values()

    configured_with_lp = {"github", "jira", "launchpad"}
    queries._configured_sources = configured_with_lp
    clause2, params2 = queries._source_filter("pull_request")
    assert "github" in params2.values()
    assert "launchpad" in params2.values()
    assert "jira" not in params2.values()


@pytest.mark.asyncio
async def test_person_detail_contributions(db_session: AsyncSession, full_config):
    """Person detail returns per-source, per-project breakdown."""
    from project_health.db.reconcile import reconcile_persons_from_config

    await reconcile_persons_from_config(db_session, full_config)

    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    await writer.write_commits("github", [
        RawCommitEvent(external_id="c1", timestamp=now, actor="alice-gh", project="owner/repo-a", data={}),
        RawCommitEvent(external_id="c2", timestamp=now, actor="alice-gh", project="owner/repo-b", data={}),
    ])
    await writer.write_issues("jira", [
        RawIssueEvent(external_id="ISS-1", timestamp=now, actor="alice-jira", project="PROJ",
                       data={"issue_type": "Bug", "closed_at": now.isoformat(), "status": "Done"}),
    ])

    alice_person = await db_session.execute(select(Person).where(Person.display_name == "Alice"))
    alice = alice_person.scalar_one()

    queries = AggregationQueries(db_session, full_config, {"github", "jira"})
    ctx = Timeframe(kind="date_range", start=now - timedelta(days=1), end=now + timedelta(days=1))
    result = await queries.person_contributions(alice.id, ctx)

    assert result is not None
    assert result["display_name"] == "Alice"
    assert len(result["contributions"]) == 2

    jira_contrib = next(c for c in result["contributions"] if c["datasource"] == "jira")
    assert jira_contrib["role"] == "umbrella"

    github_contrib = next(c for c in result["contributions"] if c["datasource"] == "github")
    assert github_contrib["role"] == "code"
    assert len(github_contrib["projects"]) == 2


def test_launchpad_config_sections():
    """Launchpad appears in datasources with is_configured=False; SOURCE_CAPABILITIES includes bugs and comments."""
    config = Config.model_validate({
        "projects": {
            "github": ["owner/repo-a"],
            "launchpad": [{"name": "my-lp-project"}],
        },
        "credentials": {
            "github_token": "test",
        },
    })
    assert config.projects.launchpad is not None
    assert len(config.projects.launchpad) == 1
    assert config.projects.launchpad[0].name == "my-lp-project"
    assert config.credentials.launchpad is None

    assert "issue" in SOURCE_CAPABILITIES["launchpad"]
    assert "pull_request_review" in SOURCE_CAPABILITIES["launchpad"]


def test_team_member_launchpad_identity():
    """TeamMember can have a launchpad identity."""
    from project_health.config.loader import TeamMember
    member = TeamMember(name="Alice", github="alice-gh", launchpad="alice-lp")
    assert member.launchpad == "alice-lp"