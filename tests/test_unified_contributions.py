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
    RawReviewCommentEvent, RawReviewDecisionEvent,
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
    """Legacy Launchpad project config remains accepted for existing consumers."""
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


@pytest.mark.asyncio
async def test_launchpad_datasource_exposes_separate_targets():
    config = Config.model_validate({
        "credentials": {"github_token": "test"},
        "launchpad-bugs": ["maas"],
        "launchpad-repos": ["~maas-committers/maas/+git/maas-release-tools"],
    })

    registry = await build_registry(config)
    lp_ds = next(ds for ds in registry.datasources if ds.id == "launchpad")

    assert lp_ds.is_configured is True
    assert lp_ds.projects == ["maas"]
    assert lp_ds.bug_targets == ["maas"]
    assert lp_ds.repositories == ["~maas-committers/maas/+git/maas-release-tools"]


@pytest.mark.asyncio
async def test_build_registry_uses_nested_launchpad_targets():
    config = Config.model_validate({
        "credentials": {"github_token": "test"},
        "projects": {
            "launchpad-bugs": ["maas"],
            "launchpad-repos": ["~maas-committers/maas/+git/maas-release-tools", "django-piston3"],
        },
    })

    registry = await build_registry(config)
    lp_ds = next(ds for ds in registry.datasources if ds.id == "launchpad")

    assert registry.get("launchpad") is not None
    assert lp_ds.is_configured is True
    assert lp_ds.bug_targets == ["maas"]
    assert lp_ds.repositories == ["~maas-committers/maas/+git/maas-release-tools", "django-piston3"]


def test_team_member_launchpad_identity():
    """TeamMember can have a launchpad identity."""
    from project_health.config.loader import TeamMember
    member = TeamMember(name="Alice", github="alice-gh", launchpad="alice-lp")
    assert member.launchpad == "alice-lp"


@pytest.mark.asyncio
async def test_launchpad_identity_details_from_config(db_session: AsyncSession):
    from project_health.db.reconcile import reconcile_persons_from_config

    config = Config.model_validate({
        "team": [{"name": "Alice", "launchpad": "~alice"}],
        "credentials": {"github_token": "test"},
    })
    await reconcile_persons_from_config(db_session, config)

    queries = AggregationQueries(db_session, config, {"launchpad"})
    now = datetime.now(timezone.utc)
    ctx = Timeframe(kind="date_range", start=now - timedelta(days=1), end=now)
    persons = await queries.list_persons(ctx)
    alice = next(p for p in persons if p["display_name"] == "Alice")

    assert alice["identities"][0]["display_name"] == "Alice"
    assert alice["identities"][0]["profile_url"] == "https://launchpad.net/~alice"


@pytest.mark.asyncio
async def test_person_aggregation_includes_launchpad_activity(db_session: AsyncSession):
    from project_health.db.reconcile import reconcile_persons_from_config

    config = Config.model_validate({
        "team": [{"name": "Alice", "launchpad": "~alice"}],
        "credentials": {"github_token": "test"},
        "launchpad-bugs": ["maas"],
        "launchpad-repos": ["~maas-committers/maas/+git/maas-release-tools"],
    })
    await reconcile_persons_from_config(db_session, config)
    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    await writer.write_issues("launchpad", [
        RawIssueEvent(
            external_id="maas:1",
            timestamp=now,
            actor="~alice",
            project="maas",
            data={"status": "Fix Committed", "completed_contribution": True, "normalized_status": "done"},
        )
    ])
    await writer.write_commits("launchpad", [
        RawCommitEvent(external_id="sha1", timestamp=now, actor="~alice", project="~maas-committers/maas/+git/maas-release-tools", data={}),
    ])
    await writer.write_pull_requests("launchpad", [
        RawPREvent(external_id="mp-1", timestamp=now, actor="~alice", project="~maas-committers/maas/+git/maas-release-tools", data={"merged_at": now.isoformat()}),
    ])
    await writer.write_review_decisions("launchpad", [
        RawReviewDecisionEvent(external_id="vote-1", timestamp=now, actor="~alice", project="~maas-committers/maas/+git/maas-release-tools", data={"normalized_state": "approved"}),
    ])
    await writer.write_review_comments("launchpad", [
        RawReviewCommentEvent(external_id="comment-1", timestamp=now, actor="~alice", project="~maas-committers/maas/+git/maas-release-tools", data={"body": "Looks good"}),
    ])

    queries = AggregationQueries(db_session, config, {"launchpad"})
    ctx = Timeframe(kind="date_range", start=now - timedelta(days=1), end=now + timedelta(days=1))
    persons = await queries.list_persons(ctx)
    alice = next(p for p in persons if p["display_name"] == "Alice")

    assert alice["metrics"]["issues_resolved"] == 1
    assert alice["metrics"]["commits"] == 1
    assert alice["metrics"]["prs_merged"] == 1
    assert alice["metrics"]["reviews_given"] == 1
    assert alice["metrics"]["review_comments"] == 1


@pytest.mark.asyncio
async def test_dual_representation_reviews_not_double_counted(db_session: AsyncSession):
    """When both pull_request_review and review_decision events exist (as in real
    ingestion), reviews_given must not be doubled."""
    from project_health.db.reconcile import reconcile_persons_from_config

    config = Config.model_validate({
        "team": [{"name": "Alice", "github": "alice-gh"}],
        "projects": {"github": ["owner/repo-a"]},
        "credentials": {"github_token": "test"},
    })
    await reconcile_persons_from_config(db_session, config)
    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    # Simulate real ingestion: same review stored as both event types
    from project_health.providers.protocol import RawReviewDecisionEvent
    await writer.write_pull_request_reviews("github", [
        RawReviewEvent(
            external_id="rev-1",
            timestamp=now,
            actor="alice-gh",
            project="owner/repo-a",
            data={"review_state": "APPROVED", "normalized_state": "approved", "comment_count": 1, "pr_external_id": "42"},
        )
    ])
    await writer.write_review_decisions("github", [
        RawReviewDecisionEvent(
            external_id="rev-1",
            timestamp=now,
            actor="alice-gh",
            project="owner/repo-a",
            data={"review_state": "APPROVED", "normalized_state": "approved", "comment_count": 1, "pr_external_id": "42"},
        )
    ])

    queries = AggregationQueries(db_session, config, {"github"})
    ctx = Timeframe(kind="date_range", start=now - timedelta(days=1), end=now + timedelta(days=1))
    persons = await queries.list_persons(ctx)
    alice = next(p for p in persons if p["display_name"] == "Alice")

    assert alice["metrics"]["reviews_given"] == 1, "review_decision counted once, pull_request_review ignored"


@pytest.mark.asyncio
async def test_velocity_review_turnaround_includes_launchpad(db_session: AsyncSession):
    """Velocity review turnaround must work for LP reviews that use
    change_request_external_id instead of pr_external_id."""
    config = Config.model_validate({
        "credentials": {"github_token": "test"},
        "launchpad-repos": ["~maas-committers/maas/+git/maas-release-tools"],
    })
    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)
    mp_ts = now - timedelta(hours=12)

    await writer.write_pull_requests("launchpad", [
        RawPREvent(
            external_id="mp-1",
            timestamp=mp_ts,
            actor="~author",
            project="~maas-committers/maas/+git/maas-release-tools",
            data={"merged_at": now.isoformat(), "state": "merged"},
        )
    ])
    from project_health.providers.protocol import RawReviewDecisionEvent
    review_ts = mp_ts + timedelta(hours=2)
    await writer.write_review_decisions("launchpad", [
        RawReviewDecisionEvent(
            external_id="vote-1",
            timestamp=review_ts,
            actor="~reviewer",
            project="~maas-committers/maas/+git/maas-release-tools",
            data={"normalized_state": "approved", "change_request_external_id": "mp-1"},
        )
    ])

    queries = AggregationQueries(db_session, config, {"launchpad"})
    ctx = Timeframe(kind="date_range", start=now - timedelta(days=1), end=now + timedelta(days=1))
    result = await queries.velocity(ctx)

    assert result["review_turnaround_median"] is not None, "LP reviews must be included in turnaround"
    assert result["review_turnaround_median"] > 0


@pytest.mark.asyncio
async def test_prs_merged_excludes_unmerged(db_session: AsyncSession):
    """prs_merged must count only PRs with merged_at, not all PRs."""
    from project_health.db.reconcile import reconcile_persons_from_config

    config = Config.model_validate({
        "team": [{"name": "Alice", "github": "alice-gh"}],
        "projects": {"github": ["owner/repo-a"]},
        "credentials": {"github_token": "test"},
    })
    await reconcile_persons_from_config(db_session, config)
    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    await writer.write_pull_requests("github", [
        RawPREvent(external_id="pr-1", timestamp=now, actor="alice-gh", project="owner/repo-a",
                    data={"merged_at": now.isoformat(), "additions": 10, "deletions": 2, "state": "closed"}),
        RawPREvent(external_id="pr-2", timestamp=now, actor="alice-gh", project="owner/repo-a",
                    data={"state": "open", "additions": 5, "deletions": 1}),
        RawPREvent(external_id="pr-3", timestamp=now, actor="alice-gh", project="owner/repo-a",
                    data={"state": "closed", "additions": 3, "deletions": 0}),
    ])

    queries = AggregationQueries(db_session, config, {"github"})
    ctx = Timeframe(kind="date_range", start=now - timedelta(days=1), end=now + timedelta(days=1))
    persons = await queries.list_persons(ctx)
    alice = next(p for p in persons if p["display_name"] == "Alice")

    assert alice["metrics"]["prs_opened"] == 3, "all PRs authored"
    assert alice["metrics"]["prs_merged"] == 1, "only merged PR counted"


@pytest.mark.asyncio
async def test_person_detail_reviews_not_overwritten(db_session: AsyncSession):
    """review_decision and review_comment must populate separate fields, not overwrite."""
    from project_health.db.reconcile import reconcile_persons_from_config
    from project_health.providers.protocol import RawReviewDecisionEvent

    config = Config.model_validate({
        "team": [{"name": "Alice", "github": "alice-gh"}],
        "projects": {"github": ["owner/repo-a"]},
        "credentials": {"github_token": "test"},
    })
    await reconcile_persons_from_config(db_session, config)
    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    await writer.write_review_decisions("github", [
        RawReviewDecisionEvent(external_id="rev-1", timestamp=now, actor="alice-gh", project="owner/repo-a",
                                data={"normalized_state": "approved", "pr_external_id": "42"}),
    ])
    await writer.write_review_comments("github", [
        RawReviewCommentEvent(external_id="comment-1", timestamp=now, actor="alice-gh", project="owner/repo-a",
                               data={"body": "Looks good", "pr_external_id": "42"}),
        RawReviewCommentEvent(external_id="comment-2", timestamp=now, actor="alice-gh", project="owner/repo-a",
                               data={"body": "One nit", "pr_external_id": "42"}),
    ])

    alice_person = await db_session.execute(select(Person).where(Person.display_name == "Alice"))
    alice = alice_person.scalar_one()

    queries = AggregationQueries(db_session, config, {"github"})
    ctx = Timeframe(kind="date_range", start=now - timedelta(days=1), end=now + timedelta(days=1))
    result = await queries.person_contributions(alice.id, ctx)

    gh_contrib = next(c for c in result["contributions"] if c["datasource"] == "github")
    proj = gh_contrib["projects"][0]
    assert proj["reviews_given"] == 1, "from review_decision events"
    assert proj["review_comments"] == 2, "from review_comment events"


@pytest.mark.asyncio
async def test_contribution_volume_per_source_no_review_double_count(db_session: AsyncSession):
    """Per-source contribution volume must not double-count reviews stored
    as both pull_request_review and review_decision."""
    config = Config.model_validate({
        "projects": {"github": ["owner/repo-a"]},
        "credentials": {"github_token": "test"},
    })
    writer = EventWriter(db_session)
    now = datetime.now(timezone.utc)

    from project_health.providers.protocol import RawReviewDecisionEvent
    await writer.write_pull_request_reviews("github", [
        RawReviewEvent(external_id="rev-1", timestamp=now, actor="bob", project="owner/repo-a",
                        data={"review_state": "APPROVED", "normalized_state": "approved", "pr_external_id": "42"}),
    ])
    await writer.write_review_decisions("github", [
        RawReviewDecisionEvent(external_id="rev-1", timestamp=now, actor="bob", project="owner/repo-a",
                                data={"review_state": "APPROVED", "normalized_state": "approved", "pr_external_id": "42"}),
    ])

    queries = AggregationQueries(db_session, config, {"github"})
    ctx = Timeframe(kind="date_range", start=now - timedelta(days=1), end=now + timedelta(days=1))
    result = await queries.contribution_volume(ctx)
    per_source = result["per_source"]

    assert per_source["github"]["review_decisions"] == 1, "counted once via review_decision"
