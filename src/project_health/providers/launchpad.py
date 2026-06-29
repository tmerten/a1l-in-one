"""Launchpad data source provider."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from xml.etree import ElementTree

import httpx

from project_health.config.loader import Config, LaunchpadRepositoryConfig
from project_health.providers.launchpad_oauth import LaunchpadOAuthCredentials, signed_headers
from project_health.providers.protocol import (
    REVIEW_CAPABILITIES,
    RawChangeRequestEvent,
    RawCommitEvent,
    RawIssueEvent,
    RawPREvent,
    RawReviewCommentEvent,
    RawReviewDecisionEvent,
    RawReviewEvent,
    RawReviewRequestEvent,
    SprintDefinition,
)

LAUNCHPAD_DONE_STATUSES = {"Fix Committed", "Fix Released"}
LAUNCHPAD_NON_FIX_TERMINAL_STATUSES = {
    "Invalid",
    "Won't Fix",
    "Expired",
    "Opinion",
    "Does Not Exist",
}
LAUNCHPAD_API_ROOT = "https://api.launchpad.net/devel"


class LaunchpadClient:
    """Small read-only Launchpad API client."""

    def __init__(self, credentials: LaunchpadOAuthCredentials | None = None) -> None:
        headers = {"Accept": "application/json"}
        if credentials:
            headers.update(signed_headers(credentials))
        self._client = httpx.AsyncClient(
            base_url=LAUNCHPAD_API_ROOT,
            headers=headers,
            timeout=httpx.Timeout(60.0),
        )
        self._git_client = httpx.AsyncClient(
            headers={"Accept": "application/atom+xml, text/xml"},
            timeout=httpx.Timeout(60.0),
        )

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        method = method.upper()
        if method not in {"GET", "HEAD"}:
            raise ValueError("LaunchpadClient only allows GET and HEAD requests")
        response = await self._client.request(method, path, params=params)
        response.raise_for_status()
        return response

    async def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        response = await self.request("GET", path, params=params)
        data: dict[str, Any] = response.json()
        return data

    async def paginate(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        data = await self.get(path, params=params)
        if "entries" not in data:
            return [data]
        entries = list(data.get("entries") or [])
        next_link = data.get("next_collection_link")
        while next_link:
            response = await self.request("GET", next_link)
            data = response.json()
            entries.extend(data.get("entries") or [])
            next_link = data.get("next_collection_link")
        return entries

    async def bug_tasks(self, target: str, since: datetime) -> list[dict[str, Any]]:
        return await self.paginate(
            f"/{target}",
            params={"ws.op": "searchTasks", "modified_since": since.isoformat(), "ws.size": "100"},
        )

    async def repository(self, repo: LaunchpadRepositoryConfig) -> dict[str, Any]:
        if repo.owner and repo.context:
            return await self.get(f"/{repo.owner}/{repo.context}/+git/{repo.repository}")
        return await self.get(f"/{repo.repository}")

    async def commits(self, repo: LaunchpadRepositoryConfig, since: datetime) -> list[dict[str, Any]]:
        if not repo.owner or not repo.context:
            return []
        repository = await self.repository(repo)
        ref = _default_ref_name(repository)
        if ref is None:
            return []
        return await self.git_atom_commits(repository, ref, since)

    async def git_atom_commits(
        self,
        repository: dict[str, Any],
        ref: str,
        since: datetime,
    ) -> list[dict[str, Any]]:
        git_url = repository.get("git_https_url")
        if not git_url:
            return []
        response = await self._git_client.get(
            f"{str(git_url).rstrip('/')}/atom/",
            params={"h": ref},
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return _atom_commit_events(response.text, since)

    async def merge_proposals(self, repo: LaunchpadRepositoryConfig, since: datetime) -> list[dict[str, Any]]:
        if not repo.owner or not repo.context:
            return await self.paginate_optional(
                f"/{repo.repository}",
                params={"ws.op": "getMergeProposals", "modified_since": since.isoformat(), "ws.size": "100"},
            )
        return await self.paginate_optional(
            f"/{repo.owner}/{repo.context}/+git/{repo.repository}",
            params={"ws.op": "getMergeProposals", "modified_since": since.isoformat(), "ws.size": "100"},
        )

    async def code_review_comments(self, merge_proposal_link: str) -> list[dict[str, Any]]:
        return await self.paginate_optional(merge_proposal_link)

    async def vote_references(self, merge_proposal_link: str) -> list[dict[str, Any]]:
        return await self.paginate_optional(merge_proposal_link)

    async def paginate_optional(
        self,
        path: str,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            return await self.paginate(path, params=params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return []
            raise

    async def person(self, name: str) -> dict[str, Any]:
        return await self.get(f"/~{name.lstrip('~')}")

    async def team(self, name: str) -> dict[str, Any]:
        return await self.get(f"/~{name.lstrip('~')}")


class LaunchpadProvider:
    """Launchpad provider for bug targets and repository targets."""

    id = "launchpad"

    def __init__(self, config: Config) -> None:
        self._bug_targets = config.all_launchpad_bug_targets
        self._repositories = config.all_launchpad_repositories
        creds = config.credentials.launchpad
        credentials = (
            LaunchpadOAuthCredentials(
                consumer_key=creds.consumer_key,
                access_token=creds.access_token,
                access_token_secret=creds.access_token_secret,
            )
            if creds
            else None
        )
        self._client = LaunchpadClient(credentials=credentials)

    async def fetch_commits(self, since: datetime) -> list[RawCommitEvent]:
        events: list[RawCommitEvent] = []
        for repo in self._repositories:
            for commit in await self._client.commits(repo, since):
                event = _commit_event(repo, commit)
                if event:
                    events.append(event)
        return events

    async def fetch_pull_requests(self, since: datetime) -> list[RawPREvent]:
        change_requests = await self.fetch_change_requests(since)
        return [
            RawPREvent(
                external_id=event.external_id,
                timestamp=event.timestamp,
                actor=event.actor,
                project=event.project,
                data=event.data,
            )
            for event in change_requests
        ]

    async def fetch_change_requests(self, since: datetime) -> list[RawChangeRequestEvent]:
        events: list[RawChangeRequestEvent] = []
        for repo in self._repositories:
            for proposal in await self._client.merge_proposals(repo, since):
                event = _merge_proposal_event(repo, proposal)
                if event:
                    events.append(event)
        return events

    async def fetch_pull_request_reviews(self, since: datetime) -> list[RawReviewEvent]:
        decisions = await self.fetch_review_decisions(since)
        return [
            RawReviewEvent(
                external_id=event.external_id,
                timestamp=event.timestamp,
                actor=event.actor,
                project=event.project,
                data=event.data,
            )
            for event in decisions
        ]

    async def fetch_review_requests(self, since: datetime) -> list[RawReviewRequestEvent]:
        events: list[RawReviewRequestEvent] = []
        for repo in self._repositories:
            for proposal in await self._client.merge_proposals(repo, since):
                votes_link = proposal.get("votes_collection_link")
                if not votes_link:
                    continue
                for vote in await self._client.vote_references(str(votes_link)):
                    event = _vote_reference_event(repo, proposal, vote)
                    if event:
                        events.append(event)
        return events

    async def fetch_review_decisions(self, since: datetime) -> list[RawReviewDecisionEvent]:
        events: list[RawReviewDecisionEvent] = []
        for repo in self._repositories:
            for proposal in await self._client.merge_proposals(repo, since):
                comments_link = proposal.get("all_comments_collection_link")
                if not comments_link:
                    continue
                for comment in await self._client.code_review_comments(str(comments_link)):
                    event = _review_decision_event(repo, proposal, comment)
                    if event:
                        events.append(event)
        return events

    async def fetch_review_comments(self, since: datetime) -> list[RawReviewCommentEvent]:
        events: list[RawReviewCommentEvent] = []
        for repo in self._repositories:
            for proposal in await self._client.merge_proposals(repo, since):
                comments_link = proposal.get("all_comments_collection_link")
                if not comments_link:
                    continue
                for comment in await self._client.code_review_comments(str(comments_link)):
                    event = _review_comment_event(repo, proposal, comment)
                    if event:
                        events.append(event)
        return events

    async def fetch_issues(self, since: datetime) -> list[RawIssueEvent]:
        events: list[RawIssueEvent] = []
        for target in self._bug_targets:
            for task in await self._client.bug_tasks(target.name, since):
                event = _bug_task_event(target.name, task)
                if event:
                    events.append(event)
        return events

    async def fetch_sprints(self) -> list[SprintDefinition]:
        return []

    async def health_check(self) -> bool:
        try:
            await self._client.request("HEAD", "/")
            return True
        except Exception:
            return False


def _bug_task_event(target: str, task: dict[str, Any]) -> RawIssueEvent | None:
    timestamp = _parse_time(task.get("date_created") or task.get("date_last_updated"))
    if timestamp is None:
        return None
    bug_id = str(task.get("bug_link") or task.get("bug") or task.get("id") or task.get("self_link"))
    task_id = str(task.get("id") or f"{target}:{bug_id}")
    status = str(task.get("status") or "Unknown")
    normalized_status = normalize_launchpad_bug_status(status)
    assignee = _identity_from_link(task.get("assignee_link") or task.get("assignee"))
    reporter = _identity_from_link(task.get("owner_link") or task.get("bug_owner_link"))
    actor = assignee or reporter
    resolved_at = task.get("date_fix_committed") or task.get("date_fix_released")
    return RawIssueEvent(
        external_id=task_id,
        timestamp=timestamp,
        actor=actor,
        project=target,
        data={
            "work_item_id": bug_id,
            "title": task.get("title") or task.get("bug_title") or bug_id,
            "description": task.get("description") or task.get("bug_description"),
            "issue_type": "bug",
            "status": status,
            "normalized_status": normalized_status,
            "completed_contribution": status in LAUNCHPAD_DONE_STATUSES,
            "priority": task.get("importance"),
            "assignee": assignee,
            "reporter": reporter,
            "milestone": task.get("milestone_link") or task.get("milestone"),
            "labels": task.get("tags") or [],
            "updated_at": task.get("date_last_updated"),
            "resolutiondate": resolved_at,
            "closed_at": task.get("date_closed"),
            "html_url": task.get("web_link") or task.get("bug_web_link") or "",
            "raw": task,
        },
    )


def _commit_event(repo: LaunchpadRepositoryConfig, commit: dict[str, Any]) -> RawCommitEvent | None:
    timestamp = _parse_time(
        commit.get("date")
        or commit.get("updated")
        or commit.get("author_date")
        or commit.get("committer_date")
    )
    if timestamp is None:
        return None
    sha = str(commit.get("sha1") or commit.get("sha") or commit.get("id"))
    return RawCommitEvent(
        external_id=sha,
        timestamp=timestamp,
        actor=_identity_from_link(commit.get("author_link")) or commit.get("author_name"),
        project=repo.path,
        data={
            "message": commit.get("message") or commit.get("title") or "",
            "author_name": commit.get("author_name"),
            "committer_name": commit.get("committer_name"),
            "html_url": commit.get("web_link", ""),
            "repository": repo.model_dump(),
            "raw": commit,
        },
    )


def _default_ref_name(repository: dict[str, Any]) -> str | None:
    branch = repository.get("default_branch")
    if not branch:
        return None
    branch_name = str(branch).removeprefix("refs/heads/").strip("/")
    return branch_name or None


def _atom_commit_events(feed: str, since: datetime) -> list[dict[str, Any]]:
    try:
        root = ElementTree.fromstring(feed)
    except ElementTree.ParseError:
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    commits: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ns):
        updated = entry.findtext("atom:updated", namespaces=ns)
        timestamp = _parse_time(updated)
        if timestamp is None or timestamp < since:
            continue
        link = entry.find("atom:link", ns)
        commits.append(
            {
                "id": entry.findtext("atom:id", namespaces=ns),
                "sha1": entry.findtext("atom:id", namespaces=ns),
                "title": entry.findtext("atom:title", namespaces=ns),
                "updated": updated,
                "author_name": entry.findtext("atom:author/atom:name", namespaces=ns),
                "web_link": link.attrib.get("href") if link is not None else None,
            }
        )
    return commits


def _merge_proposal_event(
    repo: LaunchpadRepositoryConfig,
    proposal: dict[str, Any],
) -> RawChangeRequestEvent | None:
    timestamp = _parse_time(proposal.get("date_created") or proposal.get("date_review_requested"))
    if timestamp is None:
        return None
    external_id = str(proposal.get("id") or proposal.get("self_link") or proposal.get("web_link"))
    state = normalize_launchpad_mp_state(str(proposal.get("queue_status") or "unknown"))
    return RawChangeRequestEvent(
        external_id=external_id,
        timestamp=timestamp,
        actor=_identity_from_link(proposal.get("registrant_link") or proposal.get("owner_link")),
        project=repo.path,
        data={
            "title": proposal.get("commit_message") or proposal.get("description") or external_id,
            "state": state,
            "queue_status": proposal.get("queue_status"),
            "merged_at": proposal.get("date_merged"),
            "closed_at": proposal.get("date_closed") or proposal.get("date_reviewed"),
            "source_branch": proposal.get("source_git_path") or proposal.get("source_branch_link"),
            "target_branch": proposal.get("target_git_path") or proposal.get("target_branch_link"),
            "target_repository": repo.path,
            "html_url": proposal.get("web_link", ""),
            "source_kind": "merge_proposal",
            "normalized_kind": "change_request",
            "capabilities": REVIEW_CAPABILITIES["launchpad"],
            "repository": repo.model_dump(),
            "raw": proposal,
        },
    )


def _vote_reference_event(
    repo: LaunchpadRepositoryConfig,
    proposal: dict[str, Any],
    vote: dict[str, Any],
) -> RawReviewRequestEvent | None:
    reviewer = _identity_from_link(vote.get("reviewer_link") or vote.get("registrant_link"))
    if not reviewer:
        return None
    mp_id = str(proposal.get("id") or proposal.get("self_link") or proposal.get("web_link"))
    timestamp = _parse_time(vote.get("date_created") or proposal.get("date_review_requested"))
    if timestamp is None:
        return None
    return RawReviewRequestEvent(
        external_id=f"{mp_id}:{reviewer}",
        timestamp=timestamp,
        actor=reviewer,
        project=repo.path,
        data={
            "change_request_external_id": mp_id,
            "source_kind": "vote_reference",
            "normalized_kind": "review_request",
            "reviewer_state": vote.get("vote"),
            "raw": vote,
        },
    )


def _review_decision_event(
    repo: LaunchpadRepositoryConfig,
    proposal: dict[str, Any],
    comment: dict[str, Any],
) -> RawReviewDecisionEvent | None:
    vote = comment.get("vote")
    normalized = normalize_launchpad_vote(vote)
    if normalized is None:
        return None
    timestamp = _parse_time(comment.get("date_created") or comment.get("date"))
    if timestamp is None:
        return None
    mp_id = str(proposal.get("id") or proposal.get("self_link") or proposal.get("web_link"))
    return RawReviewDecisionEvent(
        external_id=str(comment.get("id") or comment.get("self_link") or f"{mp_id}:{timestamp.isoformat()}"),
        timestamp=timestamp,
        actor=_identity_from_link(comment.get("owner_link") or comment.get("author_link")),
        project=repo.path,
        data={
            "change_request_external_id": mp_id,
            "review_state": vote,
            "normalized_state": normalized,
            "body": comment.get("content") or "",
            "source_kind": "code_review_comment_vote",
            "normalized_kind": "review_decision",
            "comment_kind": "vote_comment",
            "raw": comment,
        },
    )


def _review_comment_event(
    repo: LaunchpadRepositoryConfig,
    proposal: dict[str, Any],
    comment: dict[str, Any],
) -> RawReviewCommentEvent | None:
    content = comment.get("content")
    if not content:
        return None
    timestamp = _parse_time(comment.get("date_created") or comment.get("date"))
    if timestamp is None:
        return None
    mp_id = str(proposal.get("id") or proposal.get("self_link") or proposal.get("web_link"))
    return RawReviewCommentEvent(
        external_id=str(comment.get("id") or comment.get("self_link") or f"{mp_id}:{timestamp.isoformat()}"),
        timestamp=timestamp,
        actor=_identity_from_link(comment.get("owner_link") or comment.get("author_link")),
        project=repo.path,
        data={
            "change_request_external_id": mp_id,
            "body": content,
            "source_kind": "code_review_comment",
            "normalized_kind": "review_comment",
            "comment_kind": "vote_comment" if comment.get("vote") else "discussion_comment",
            "is_inline": None,
            "raw": comment,
        },
    )


def normalize_launchpad_bug_status(status: str) -> str:
    return {
        "New": "open",
        "Confirmed": "open",
        "Triaged": "ready",
        "Incomplete": "needs_information",
        "In Progress": "in_progress",
        "Fix Committed": "done",
        "Fix Released": "done",
        "Invalid": "cancelled",
        "Won't Fix": "cancelled",
        "Expired": "cancelled",
        "Opinion": "non_actionable",
        "Deferred": "deferred",
        "Does Not Exist": "cancelled",
    }.get(status, "unknown")


def normalize_launchpad_vote(vote: object) -> str | None:
    if not vote:
        return None
    return {
        "Approve": "approved",
        "Needs Fixing": "changes_requested",
        "Needs Resubmitting": "changes_requested",
        "Needs Information": "needs_information",
        "Disapprove": "rejected",
        "Abstain": "neutral",
    }.get(str(vote))


def normalize_launchpad_mp_state(queue_status: str) -> str:
    lower = queue_status.lower()
    if lower in {"merged", "merged proposal"}:
        return "merged"
    if lower in {"rejected", "superseded"}:
        return "superseded"
    if lower in {"work in progress", "needs review", "approved"}:
        return "open"
    if lower in {"closed", "abandoned"}:
        return "closed"
    return "unknown"


def _parse_time(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _identity_from_link(value: object) -> str | None:
    if not value:
        return None
    text = str(value).rstrip("/")
    return text.rsplit("/", 1)[-1]
