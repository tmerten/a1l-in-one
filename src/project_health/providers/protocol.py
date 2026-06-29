"""Provider interface protocol, datasource models, and event models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class DatasourceRole(StrEnum):
    UMBRELLA = "umbrella"
    CODE = "code"


class Datasource(BaseModel):
    id: str
    role: DatasourceRole
    display_name: str
    projects: list[str] = Field(default_factory=list)
    bug_targets: list[str] = Field(default_factory=list)
    repositories: list[str] = Field(default_factory=list)
    is_configured: bool = False


SOURCE_CAPABILITIES: dict[str, set[str]] = {
    "github": {
        "commit",
        "pull_request",
        "pull_request_review",
        "issue",
        "change_request",
        "review_request",
        "review_decision",
        "review_comment",
    },
    "jira": {"issue", "sprint"},
    "launchpad": {
        "pull_request",
        "pull_request_review",
        "commit",
        "issue",
        "change_request",
        "review_request",
        "review_decision",
        "review_comment",
    },
}


REVIEW_CAPABILITIES: dict[str, dict[str, object]] = {
    "github": {
        "review_comments": True,
        "inline_comments": True,
        "review_requests": True,
        "review_decisions": True,
        "approval_state": "native",
    },
    "launchpad": {
        "review_comments": True,
        "inline_comments": "unknown",
        "review_requests": True,
        "review_decisions": True,
        "approval_state": "source_specific",
    },
}


def sources_for_event_type(event_type: str, configured_sources: set[str]) -> set[str]:
    return {
        source
        for source in configured_sources
        if event_type in SOURCE_CAPABILITIES.get(source, set())
    }


class RawCommitEvent(BaseModel):
    """A commit event from a data source."""

    external_id: str = Field(..., description="Source-native commit SHA")
    timestamp: datetime = Field(..., description="Commit timestamp")
    actor: str | None = Field(default=None, description="Author identifier")
    project: str = Field(..., description="Repository or project identifier")
    data: dict = Field(default_factory=dict)


class RawPREvent(BaseModel):
    """A pull request / merge proposal event."""

    external_id: str = Field(..., description="Source-native PR number/ID")
    timestamp: datetime = Field(..., description="PR created_at")
    actor: str | None = Field(default=None, description="Author identifier")
    project: str = Field(..., description="Repository or project identifier")
    data: dict = Field(default_factory=dict)


class RawReviewEvent(BaseModel):
    """A pull request review event."""

    external_id: str = Field(..., description="Source-native review ID")
    timestamp: datetime = Field(..., description="Review submitted timestamp")
    actor: str | None = Field(default=None, description="Reviewer identifier")
    project: str = Field(..., description="Repository or project identifier")
    data: dict = Field(default_factory=dict)


class RawChangeRequestEvent(BaseModel):
    """A provider-neutral change request event."""

    external_id: str = Field(..., description="Source-native change request ID")
    timestamp: datetime = Field(..., description="Change request creation timestamp")
    actor: str | None = Field(default=None, description="Author identifier")
    project: str = Field(..., description="Repository or project identifier")
    data: dict = Field(default_factory=dict)


class RawReviewRequestEvent(BaseModel):
    """A provider-neutral review request event."""

    external_id: str = Field(..., description="Source-native review request ID")
    timestamp: datetime = Field(..., description="Review request timestamp")
    actor: str | None = Field(default=None, description="Reviewer identifier")
    project: str = Field(..., description="Repository or project identifier")
    data: dict = Field(default_factory=dict)


class RawReviewDecisionEvent(BaseModel):
    """A provider-neutral review decision event."""

    external_id: str = Field(..., description="Source-native review decision ID")
    timestamp: datetime = Field(..., description="Review decision timestamp")
    actor: str | None = Field(default=None, description="Reviewer identifier")
    project: str = Field(..., description="Repository or project identifier")
    data: dict = Field(default_factory=dict)


class RawReviewCommentEvent(BaseModel):
    """A provider-neutral review comment event."""

    external_id: str = Field(..., description="Source-native review comment ID")
    timestamp: datetime = Field(..., description="Review comment timestamp")
    actor: str | None = Field(default=None, description="Comment author identifier")
    project: str = Field(..., description="Repository or project identifier")
    data: dict = Field(default_factory=dict)


class RawIssueEvent(BaseModel):
    """An issue event (GitHub issue or Jira ticket)."""

    external_id: str = Field(..., description="Source-native issue key/ID")
    timestamp: datetime = Field(..., description="Issue created/updated timestamp")
    actor: str | None = Field(default=None, description="Reporter/assignee identifier")
    project: str = Field(..., description="Repository or project key")
    data: dict = Field(default_factory=dict)


class SprintDefinition(BaseModel):
    """A sprint definition from a data source."""

    id: str = Field(..., description="Source-native sprint ID")
    name: str = Field(..., description="Sprint name")
    project: str = Field(..., description="Project key")
    start_date: datetime = Field(..., description="Sprint start date")
    end_date: datetime = Field(..., description="Sprint end date")
    state: str = Field(default="active", description="active | closed | future")


@runtime_checkable
class DataSourceProvider(Protocol):
    """Protocol for data source providers (GitHub, Jira, Launchpad)."""

    id: str  # "github", "jira", "launchpad"

    async def fetch_commits(self, since: datetime) -> list[RawCommitEvent]:
        """Fetch commits created/updated since `since`."""
        ...

    async def fetch_pull_requests(self, since: datetime) -> list[RawPREvent]:
        """Fetch pull requests created/updated since `since`."""
        ...

    async def fetch_change_requests(self, since: datetime) -> list[RawChangeRequestEvent]:
        """Fetch provider-neutral change requests created/updated since `since`."""
        ...

    async def fetch_pull_request_reviews(self, since: datetime) -> list[RawReviewEvent]:
        """Fetch PR reviews submitted since `since`."""
        ...

    async def fetch_review_requests(self, since: datetime) -> list[RawReviewRequestEvent]:
        """Fetch provider-neutral review requests created/updated since `since`."""
        ...

    async def fetch_review_decisions(self, since: datetime) -> list[RawReviewDecisionEvent]:
        """Fetch provider-neutral review decisions submitted since `since`."""
        ...

    async def fetch_review_comments(self, since: datetime) -> list[RawReviewCommentEvent]:
        """Fetch provider-neutral review comments submitted since `since`."""
        ...

    async def fetch_issues(self, since: datetime) -> list[RawIssueEvent]:
        """Fetch issues created/updated since `since`."""
        ...

    async def fetch_sprints(self) -> list[SprintDefinition]:
        """Fetch sprint definitions."""
        ...

    async def health_check(self) -> bool:
        """Verify credentials and API reachability."""
        ...
