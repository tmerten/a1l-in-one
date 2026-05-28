"""Jira data source provider."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from project_health.config.loader import Config
from project_health.providers.protocol import (
    RawCommitEvent,
    RawIssueEvent,
    RawPREvent,
    RawReviewEvent,
    SprintDefinition,
)


class JiraProvider:
    """Jira REST API provider for issues and sprints."""

    id = "jira"

    def __init__(self, config: Config) -> None:
        self._creds = config.credentials.jira
        self._projects = config.all_jira_projects
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            if self._creds is None:
                raise RuntimeError("Jira credentials not configured")
            auth = httpx.BasicAuth(self._creds.email, self._creds.api_token)
            self._client = httpx.AsyncClient(
                base_url=self._creds.base_url.rstrip("/"),
                auth=auth,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(60.0),
            )
        return self._client

    # ------------------------------------------------------------------
    # 6.2 fetch_issues
    # ------------------------------------------------------------------
    async def fetch_issues(self, since: datetime) -> list[RawIssueEvent]:
        client = await self._get_client()
        events: list[RawIssueEvent] = []
        since_str = since.strftime("%Y-%m-%d %H:%M")

        import logging
        _logger = logging.getLogger(__name__)

        for proj in self._projects:
            jql = f'project = "{proj.key}" AND updated >= "{since_str}" ORDER BY updated DESC'
            _logger.warning("Jira fetch_issues JQL: %s", jql)
            issues = await self._paginate(client, "/rest/api/3/search/jql", jql=jql)
            _logger.warning("Jira fetch_issues for %s: %d issues returned", proj.key, len(issues))
            for issue in issues:
                fields = issue.get("fields", {})
                created_ts = datetime.fromisoformat(
                    fields["created"].replace("Z", "+00:00")
                )
                events.append(
                    RawIssueEvent(
                        external_id=issue["key"],
                        timestamp=created_ts,
                        actor=self._extract_actor(fields),
                        project=proj.key,
                        data={
                            "summary": fields.get("summary", ""),
                            "issue_type": fields.get("issuetype", {}).get("name", ""),
                            "story_points": self._extract_story_points(fields),
                            "status": fields.get("status", {}).get("name", ""),
                            "labels": fields.get("labels", []),
                            "description": self._extract_description(fields),
                            "updated": fields.get("updated"),
                            "resolutiondate": fields.get("resolutiondate"),
                            "assignee": fields.get("assignee", {}).get("accountId")
                                if fields.get("assignee")
                                else None,
                        },
                    )
                )
        return events

    # ------------------------------------------------------------------
    # 6.3 fetch_sprints
    # ------------------------------------------------------------------
    async def fetch_sprints(self) -> list[SprintDefinition]:
        client = await self._get_client()
        sprints: list[SprintDefinition] = []

        for proj in self._projects:
            try:
                board_resp = await client.get(
                    f"/rest/agile/1.0/board/{proj.board_id}/sprint",
                    params={"state": "active,future,closed", "maxResults": "100"},
                )
                if board_resp.status_code != 200:
                    continue
                data = board_resp.json()
                for sprint in data.get("values", []):
                    start = sprint.get("startDate")
                    end = sprint.get("endDate")
                    if not start or not end:
                        continue
                    sprints.append(
                        SprintDefinition(
                            id=str(sprint["id"]),
                            name=sprint["name"],
                            project=proj.key,
                            start_date=datetime.fromisoformat(start.replace("Z", "+00:00")),
                            end_date=datetime.fromisoformat(end.replace("Z", "+00:00")),
                            state=sprint.get("state", "unknown"),
                        )
                    )
            except httpx.HTTPError as exc:
                import logging
                logging.getLogger(__name__).warning(
                    "Sprint fetch failed for board %s: %s", proj.board_id, exc
                )
                continue
        return sprints

    # ------------------------------------------------------------------
    # 6.4 health_check
    # ------------------------------------------------------------------
    async def health_check(self) -> bool:
        client = await self._get_client()
        try:
            resp = await client.get("/rest/api/3/myself")
            if resp.status_code == 200:
                # Verify project access
                if self._projects:
                    proj = self._projects[0]
                    proj_resp = await client.get(
                        f'/rest/api/3/project/{proj.key}',
                    )
                    return proj_resp.status_code == 200
                return True
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 6.5 Unsupported event types
    # ------------------------------------------------------------------
    async def fetch_commits(self, _since: datetime) -> list[RawCommitEvent]:
        return []

    async def fetch_pull_requests(self, _since: datetime) -> list[RawPREvent]:
        return []

    async def fetch_pull_request_reviews(self, _since: datetime) -> list[RawReviewEvent]:
        return []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _paginate(
        self,
        client: httpx.AsyncClient,
        path: str,
        jql: str,
    ) -> list[dict[str, Any]]:
        import logging
        _logger = logging.getLogger(__name__)

        max_results = 100
        all_issues: list[dict[str, Any]] = []
        next_page_token: str | None = None

        while True:
            params: dict[str, str] = {
                "jql": jql,
                "maxResults": str(max_results),
                "fields": "summary,issuetype,status,labels,created,updated,reporter,assignee,customfield_10016,description",
            }
            if next_page_token:
                params["nextPageToken"] = next_page_token

            resp = await client.get(path, params=params)
            if resp.status_code != 200:
                _logger.warning("Jira API returned %d: %s", resp.status_code, resp.text[:500])
                break
            data = resp.json()
            issues = data.get("issues", [])
            if not issues:
                break
            all_issues.extend(issues)

            # v3 /search/jql uses nextPageToken; v2 used startAt/total
            if data.get("isLast", True):
                break
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

        return all_issues

    def _extract_actor(self, fields: dict[str, Any]) -> str | None:
        """Extract actor from reporter or assignee."""
        reporter = fields.get("reporter")
        if reporter:
            return reporter.get("accountId")
        assignee = fields.get("assignee")
        if assignee:
            return assignee.get("accountId")
        return None

    def _extract_story_points(self, fields: dict[str, Any]) -> float | None:
        """Extract story points from custom field."""
        # Jira often uses customfield_10016 for story points; try common fields
        for key in ("customfield_10016", "customfield_10004", "customfield_10000"):
            val = fields.get(key)
            if val is not None and isinstance(val, (int, float)):
                return float(val)
        return None

    def _extract_description(self, fields: dict[str, Any]) -> str:
        """Extract plain-text description from Jira's ADF format."""
        desc = fields.get("description")
        if desc is None:
            return ""
        if isinstance(desc, str):
            return desc
        # Minimal ADF to text (v1)
        if isinstance(desc, dict):
            return desc.get("text", "")
        return ""
