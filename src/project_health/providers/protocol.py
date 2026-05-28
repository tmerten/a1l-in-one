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
    is_configured: bool = False


SOURCE_CAPABILITIES: dict[str, set[str]] = {
    "github": {"commit", "pull_request", "pull_request_review", "issue"},
    "jira": {"issue", "sprint"},
    "launchpad": {"pull_request", "pull_request_review", "commit", "issue"},
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

    async def fetch_pull_request_reviews(self, since: datetime) -> list[RawReviewEvent]:
        """Fetch PR reviews submitted since `since`."""
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
