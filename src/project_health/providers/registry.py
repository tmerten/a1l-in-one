"""DataSourceRegistry — instantiates providers from validated config."""

from __future__ import annotations

from project_health.config.loader import Config
from project_health.providers.protocol import DataSourceProvider


class DataSourceRegistry:
    """Holds active data source providers keyed by source id."""

    def __init__(self, providers: list[DataSourceProvider]) -> None:
        self._providers: dict[str, DataSourceProvider] = {p.id: p for p in providers}

    def get(self, source_id: str) -> DataSourceProvider | None:
        return self._providers.get(source_id)

    def all(self) -> list[DataSourceProvider]:
        return list(self._providers.values())

    def sources(self) -> list[str]:
        return list(self._providers.keys())


async def build_registry(config: Config) -> DataSourceRegistry:
    """Instantiate providers from validated config.

    Only creates providers for sources that have projects configured
    and credentials present.
    """
    providers: list[DataSourceProvider] = []

    if config.projects.github:
        from project_health.providers.github import GitHubProvider
        providers.append(GitHubProvider(config))

    if config.projects.jira:
        from project_health.providers.jira import JiraProvider
        providers.append(JiraProvider(config))

    return DataSourceRegistry(providers)
