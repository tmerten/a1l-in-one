"""DataSourceRegistry — instantiates providers and builds datasource metadata from config."""

from __future__ import annotations

from project_health.config.loader import Config
from project_health.providers.protocol import Datasource, DataSourceProvider, DatasourceRole


class DataSourceRegistry:
    """Holds active data source providers and datasource metadata keyed by source id."""

    def __init__(
        self,
        providers: list[DataSourceProvider],
        datasources: list[Datasource],
    ) -> None:
        self._providers: dict[str, DataSourceProvider] = {p.id: p for p in providers}
        self._datasources: list[Datasource] = datasources

    def get(self, source_id: str) -> DataSourceProvider | None:
        return self._providers.get(source_id)

    def all(self) -> list[DataSourceProvider]:
        return list(self._providers.values())

    def sources(self) -> list[str]:
        return list(self._providers.keys())

    @property
    def datasources(self) -> list[Datasource]:
        return self._datasources

    def configured_sources(self) -> set[str]:
        return {ds.id for ds in self._datasources if ds.is_configured}


async def build_registry(config: Config) -> DataSourceRegistry:
    providers: list[DataSourceProvider] = []

    github_configured = bool(config.projects.github) and bool(config.credentials.github_token)
    jira_configured = bool(config.projects.jira) and bool(config.credentials.jira)

    if github_configured:
        from project_health.providers.github import GitHubProvider
        providers.append(GitHubProvider(config))

    if jira_configured:
        from project_health.providers.jira import JiraProvider
        providers.append(JiraProvider(config))

    launchpad_projects = [p.name for p in (config.projects.launchpad or [])]
    launchpad_configured = bool(launchpad_projects) and bool(config.credentials.launchpad)

    datasources = [
        Datasource(
            id="jira",
            role=DatasourceRole.UMBRELLA,
            display_name="Jira",
            projects=[p.key for p in config.projects.jira],
            is_configured=jira_configured,
        ),
        Datasource(
            id="github",
            role=DatasourceRole.CODE,
            display_name="GitHub",
            projects=[p.repo for p in config.projects.github],
            is_configured=github_configured,
        ),
        Datasource(
            id="launchpad",
            role=DatasourceRole.CODE,
            display_name="Launchpad",
            projects=launchpad_projects,
            is_configured=launchpad_configured,
        ),
    ]

    return DataSourceRegistry(providers, datasources)
