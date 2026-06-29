"""Pydantic models for the YAML configuration file."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

ENV_REF_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _resolve_env_refs(value: str) -> str:
    """Resolve ${ENV_VAR} references in a string."""
    def replacer(match: re.Match[str]) -> str:
        var_name = match.group(1)
        var_value = os.environ.get(var_name)
        if var_value is None:
            raise ValueError(f"Environment variable ${var_name} is not set")
        return var_value

    return ENV_REF_PATTERN.sub(replacer, value)


def _resolve_env_in_data(data: object) -> object:
    """Recursively resolve ${ENV_VAR} references in dict/list primitives."""
    if isinstance(data, str):
        return _resolve_env_refs(data)
    if isinstance(data, dict):
        return {k: _resolve_env_in_data(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_resolve_env_in_data(item) for item in data]
    return data


class TeamMember(BaseModel):
    """A team member with per-source identities."""

    name: str = Field(..., description="Display name")
    github: str | None = Field(default=None, description="GitHub username")
    jira: str | None = Field(default=None, description="Jira accountId")
    launchpad: str | None = Field(default=None, description="Launchpad username")


class GithubProject(BaseModel):
    """GitHub repository reference."""

    repo: str = Field(..., description="owner/repo format")


class JiraProject(BaseModel):
    """Jira project/board reference."""

    key: str = Field(..., description="Jira project key")
    board_id: int = Field(..., description="Board ID for sprint integration")


class LaunchpadConfig(BaseModel):
    """Launchpad API settings."""

    model_config = ConfigDict(extra="forbid")


class LaunchpadBugTargetConfig(BaseModel):
    """Launchpad bug target reference."""

    name: str = Field(..., description="Launchpad bug target name")
    display_name: str | None = Field(default=None)
    statuses: list[str] | None = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def _coerce_string(cls, value: object) -> object:
        if isinstance(value, str):
            return {"name": value}
        return value


class LaunchpadRepositoryConfig(BaseModel):
    """Launchpad Git repository reference."""

    path: str = Field(..., description="Canonical ~owner/context/+git/repository path")
    owner: str | None = Field(default=None, description="Launchpad person/team owner")
    context: str | None = Field(default=None, description="Launchpad project or context")
    repository: str = Field(..., description="Launchpad repository name")
    display_name: str | None = Field(default=None)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        if "/+git/" in value:
            parse_launchpad_repo_path(value)
        return value

    @model_validator(mode="before")
    @classmethod
    def _coerce_and_parse(cls, value: object) -> object:
        if isinstance(value, str):
            if "/+git/" not in value:
                return {
                    "path": value,
                    "owner": None,
                    "context": None,
                    "repository": value,
                }
            owner, context, repository = parse_launchpad_repo_path(value)
            return {
                "path": value,
                "owner": owner,
                "context": context,
                "repository": repository,
            }
        if isinstance(value, dict) and "path" in value:
            path = str(value["path"])
            if "/+git/" not in path:
                return {
                    **value,
                    "owner": value.get("owner"),
                    "context": value.get("context"),
                    "repository": value.get("repository", path),
                }
            owner, context, repository = parse_launchpad_repo_path(path)
            return {
                **value,
                "owner": value.get("owner", owner),
                "context": value.get("context", context),
                "repository": value.get("repository", repository),
            }
        return value


def parse_launchpad_repo_path(path: str) -> tuple[str, str, str]:
    """Parse a canonical Launchpad Git repo path into owner, context, repository."""
    match = re.fullmatch(r"(?P<owner>~[^/]+)/(?P<context>[^/]+)/\+git/(?P<repo>[^/]+)", path)
    if match is None:
        raise ValueError(
            "Launchpad repository paths must use '~owner/context/+git/repository' format"
        )
    return match.group("owner"), match.group("context"), match.group("repo")


class JiraCredentials(BaseModel):
    """Jira API credentials."""

    base_url: str = Field(..., description="Jira base URL, e.g. https://company.atlassian.net")
    email: str = Field(..., description="Jira user email")
    api_token: str = Field(..., description="Jira API token")


class LaunchpadCredentials(BaseModel):
    """Launchpad API credentials."""

    consumer_key: str = Field(..., description="Launchpad OAuth consumer key")
    access_token: str = Field(..., description="Launchpad OAuth access token")
    access_token_secret: str = Field(..., description="Launchpad OAuth access token secret")


class Credentials(BaseModel):
    """API credentials with env-var resolution."""

    github_token: str = Field(..., description="GitHub personal access token")
    jira: JiraCredentials | None = Field(default=None)
    launchpad: LaunchpadCredentials | None = Field(default=None)


class IngestionSettings(BaseModel):
    """Ingestion scheduler settings."""

    interval_minutes: int = Field(default=15, ge=1, description="Scheduler interval in minutes")
    backfill_days: int = Field(default=90, ge=1, description="Default backfill window in days")


class IssueTypeMapping(BaseModel):
    """Per-source issue type normalization mapping."""

    github: dict[str, str] = Field(default_factory=dict)
    jira: dict[str, str] = Field(default_factory=dict)


class BotsConfig(BaseModel):
    """Bot identities to exclude from human metrics."""

    github: list[str] = Field(
        default_factory=lambda: [
            "dependabot[bot]",
            "renovate[bot]",
            "github-actions[bot]",
        ]
    )
    launchpad: list[str] = Field(default_factory=list)


class Config(BaseModel):
    """Root configuration object."""

    team: list[TeamMember] = Field(default_factory=list)
    projects: ProjectsConfig = Field(default_factory=lambda: ProjectsConfig.model_validate({}))
    launchpad: LaunchpadConfig = Field(default_factory=lambda: LaunchpadConfig.model_validate({}))
    launchpad_bugs: list[LaunchpadBugTargetConfig] = Field(
        default_factory=list,
        validation_alias=AliasChoices("launchpad-bugs", "launchpad_bugs"),
    )
    launchpad_repos: list[LaunchpadRepositoryConfig] = Field(
        default_factory=list,
        validation_alias=AliasChoices("launchpad-repos", "launchpad_repos"),
    )
    credentials: Credentials
    ingestion: IngestionSettings = Field(default_factory=lambda: IngestionSettings.model_validate({}))
    issue_type_mapping: IssueTypeMapping = Field(
        default_factory=lambda: IssueTypeMapping.model_validate({})
    )
    bots: BotsConfig = Field(default_factory=lambda: BotsConfig.model_validate({}))

    @model_validator(mode="before")
    @classmethod
    def _pull_nested_launchpad_targets(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        projects = data.get("projects")
        if not isinstance(projects, dict):
            return data
        normalized = dict(data)
        if "launchpad-bugs" not in normalized and "launchpad_bugs" not in normalized:
            nested_bugs = projects.get("launchpad-bugs") or projects.get("launchpad_bugs")
            if nested_bugs is not None:
                normalized["launchpad-bugs"] = nested_bugs
        if "launchpad-repos" not in normalized and "launchpad_repos" not in normalized:
            nested_repos = projects.get("launchpad-repos") or projects.get("launchpad_repos")
            if nested_repos is not None:
                normalized["launchpad-repos"] = nested_repos
        return normalized

    @model_validator(mode="after")
    def _validate_credentials_match_projects(self) -> Config:
        """Ensure credentials are present for configured project sources."""
        if self.projects.github and not self.credentials.github_token:
            raise ValueError("GitHub projects configured but github_token is missing")
        if self.projects.jira and (not self.credentials.jira):
            raise ValueError("Jira projects configured but jira credentials are missing")
        return self

    @property
    def all_github_repos(self) -> list[str]:
        return [p.repo for p in self.projects.github]

    @property
    def all_jira_projects(self) -> list[JiraProject]:
        return self.projects.jira

    @property
    def all_launchpad_bug_targets(self) -> list[LaunchpadBugTargetConfig]:
        return self.launchpad_bugs

    @property
    def all_launchpad_repositories(self) -> list[LaunchpadRepositoryConfig]:
        return self.launchpad_repos

    @property
    def github_bots(self) -> set[str]:
        return set(self.bots.github)

    @property
    def launchpad_bots(self) -> set[str]:
        return set(self.bots.launchpad)

    @model_validator(mode="after")
    def _validate_launchpad_targets(self) -> Config:
        repo_paths = [repo.path for repo in self.launchpad_repos]
        if len(repo_paths) != len(set(repo_paths)):
            raise ValueError("Duplicate Launchpad repository targets are not allowed")
        return self


class ProjectsConfig(BaseModel):
    """Project declarations per source."""

    github: list[GithubProject] = Field(default_factory=list)
    jira: list[JiraProject] = Field(default_factory=list)
    launchpad: list[LaunchpadBugTargetConfig] | None = Field(default=None)

    @field_validator("github", mode="before")
    @classmethod
    def _coerce_github_strings(cls, v: object) -> list[dict[str, str]] | object:
        if isinstance(v, list) and v and isinstance(v[0], str):
            return [{"repo": repo} for repo in v]
        return v


def load_config(path: Path) -> Config:
    """Load and validate configuration from a YAML file.

    Args:
        path: Path to the YAML config file.

    Returns:
        Validated Config instance.

    Raises:
        ValueError: If the file is missing, malformed, or missing required env vars.
    """
    if not path.exists():
        raise ValueError(f"Config file not found: {path}")

    raw_text = path.read_text()
    try:
        raw_data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Malformed YAML in {path}: {exc}") from exc

    if raw_data is None:
        raw_data = {}

    resolved = _resolve_env_in_data(raw_data)
    return Config.model_validate(resolved)
