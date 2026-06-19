"""GitHub data source provider."""

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


class GitHubProvider:
    """GitHub REST API provider for commits, PRs, PR reviews, and issues."""

    id = "github"

    def __init__(self, config: Config) -> None:
        self._token = config.credentials.github_token
        self._repos = config.all_github_repos
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=httpx.Timeout(60.0),
            )
        return self._client

    # ------------------------------------------------------------------
    # 5.2 fetch_commits
    # ------------------------------------------------------------------
    async def fetch_commits(self, since: datetime) -> list[RawCommitEvent]:
        """Fetch commits from PRs (not main branch traversal) since `since`."""
        # For v1: we fetch PRs and then list their commits to avoid double-counting squash merges
        # A simpler approach: fetch recent PRs, then list commits per PR
        client = await self._get_client()
        events: list[RawCommitEvent] = []

        for repo in self._repos:
            # Get PRs updated since `since` — we'll pull commits from these
            prs = await self._paginate(
                client,
                f"/repos/{repo}/pulls",
                params={"state": "all", "sort": "updated", "direction": "desc", "per_page": "100"},
            )
            for pr in prs:
                pr_updated = datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00"))
                if pr_updated < since:
                    break  # PRs sorted by updated desc
                # Fetch commits for this PR
                commits = await self._paginate(
                    client, f"/repos/{repo}/pulls/{pr['number']}/commits"
                )
                for commit in commits:
                    commit_ts = datetime.fromisoformat(
                        commit["commit"]["committer"]["date"].replace("Z", "+00:00")
                    )
                    if commit_ts >= since:
                        events.append(
                            RawCommitEvent(
                                external_id=commit["sha"],
                                timestamp=commit_ts,
                                actor=commit.get("author", {}).get("login")
                                    if commit.get("author")
                                    else None,
                                project=repo,
                                data={
                                    "message": commit["commit"]["message"],
                                    "pr_number": pr["number"],
                                    "author_name": commit["commit"]["author"]["name"],
                                    "committer_name": commit["commit"]["committer"]["name"],
                                    "html_url": f"https://github.com/{repo}/commit/{commit['sha']}",
                                },
                            )
                        )
        return events

    # ------------------------------------------------------------------
    # 5.3 fetch_pull_requests
    # ------------------------------------------------------------------
    async def fetch_pull_requests(self, since: datetime) -> list[RawPREvent]:
        client = await self._get_client()
        events: list[RawPREvent] = []

        for repo in self._repos:
            prs = await self._paginate(
                client,
                f"/repos/{repo}/pulls",
                params={"state": "all", "sort": "updated", "direction": "desc", "per_page": "100"},
            )
            for pr in prs:
                pr_updated = datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00"))
                if pr_updated < since:
                    break
                # Get per-file diff stats for linguist filtering
                filtered_adds, filtered_dels = await self._get_filtered_pr_stats(
                    client, repo, pr["number"]
                )
                reviewers = [r["login"] for r in pr.get("requested_reviewers", [])]
                events.append(
                    RawPREvent(
                        external_id=str(pr["number"]),
                        timestamp=datetime.fromisoformat(
                            pr["created_at"].replace("Z", "+00:00")
                        ),
                        actor=pr["user"]["login"] if pr.get("user") else None,
                        project=repo,
                        data={
                            "title": pr["title"],
                            "state": pr["state"],
                            "merged_at": pr.get("merged_at"),
                            "additions": pr.get("additions", 0),
                            "deletions": pr.get("deletions", 0),
                            "linguist_filtered_additions": filtered_adds,
                            "linguist_filtered_deletions": filtered_dels,
                            "reviewers": reviewers,
                            "draft": pr.get("draft", False),
                            "html_url": pr["html_url"],
                        },
                    )
                )
        return events

    # ------------------------------------------------------------------
    # 5.4 fetch_pull_request_reviews
    # ------------------------------------------------------------------
    async def fetch_pull_request_reviews(self, since: datetime) -> list[RawReviewEvent]:
        client = await self._get_client()
        events: list[RawReviewEvent] = []

        for repo in self._repos:
            # Get PRs updated since `since` that might have new reviews
            prs = await self._paginate(
                client,
                f"/repos/{repo}/pulls",
                params={"state": "all", "sort": "updated", "direction": "desc", "per_page": "100"},
            )
            for pr in prs:
                pr_updated = datetime.fromisoformat(pr["updated_at"].replace("Z", "+00:00"))
                if pr_updated < since:
                    break
                reviews = await self._paginate(
                    client, f"/repos/{repo}/pulls/{pr['number']}/reviews"
                )
                for review in reviews:
                    review_ts_str = review.get("submitted_at")
                    if not review_ts_str:
                        continue
                    review_ts = datetime.fromisoformat(review_ts_str.replace("Z", "+00:00"))
                    if review_ts >= since:
                        # Count inline comments on this review
                        comments = await self._paginate(
                            client,
                            f"/repos/{repo}/pulls/{pr['number']}/reviews/{review['id']}/comments",
                        )
                        events.append(
                            RawReviewEvent(
                                external_id=str(review["id"]),
                                timestamp=review_ts,
                                actor=review["user"]["login"] if review.get("user") else None,
                                project=repo,
                                data={
                                    "review_state": review["state"],  # APPROVED, CHANGES_REQUESTED, COMMENTED
                                    "comment_count": len(comments),
                                    "pr_external_id": str(pr["number"]),
                                    "body": review.get("body", ""),
                                    "html_url": f"https://github.com/{repo}/pull/{pr['number']}#pullrequestreview-{review['id']}",
                                },
                            )
                        )
        return events

    # ------------------------------------------------------------------
    # 5.5 fetch_issues
    # ------------------------------------------------------------------
    async def fetch_issues(self, since: datetime) -> list[RawIssueEvent]:
        client = await self._get_client()
        events: list[RawIssueEvent] = []

        for repo in self._repos:
            # issues endpoint includes PRs — filter them out
            issues = await self._paginate(
                client,
                f"/repos/{repo}/issues",
                params={
                    "state": "all",
                    "since": since.isoformat().replace("+00:00", "Z"),
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": "100",
                },
            )
            for issue in issues:
                # GitHub PRs have a 'pull_request' key — skip them
                if "pull_request" in issue:
                    continue
                events.append(
                    RawIssueEvent(
                        external_id=str(issue["number"]),
                        timestamp=datetime.fromisoformat(
                            issue["created_at"].replace("Z", "+00:00")
                        ),
                        actor=issue["user"]["login"] if issue.get("user") else None,
                        project=repo,
                        data={
                            "title": issue["title"],
                            "state": issue["state"],
                            "labels": [label["name"] for label in issue.get("labels", [])],
                            "body": issue.get("body", ""),
                            "updated_at": issue["updated_at"],
                            "closed_at": issue.get("closed_at"),
                            "html_url": issue["html_url"],
                        },
                    )
                )
        return events

    # ------------------------------------------------------------------
    # 5.6 health_check
    # ------------------------------------------------------------------
    async def health_check(self) -> bool:
        client = await self._get_client()
        try:
            resp = await client.get("/user")
            if resp.status_code == 200:
                # Also verify repo access by checking first repo
                if self._repos:
                    owner_repo = self._repos[0]
                    repo_resp = await client.get(f"/repos/{owner_repo}")
                    return repo_resp.status_code == 200
                return True
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 5.7 fetch_sprints — GitHub has no sprints
    # ------------------------------------------------------------------
    async def fetch_sprints(self) -> list[SprintDefinition]:
        return []

    # ------------------------------------------------------------------
    # 5.8 Rate limit handling + retry
    # ------------------------------------------------------------------
    async def _paginate(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """Paginate through GitHub API with rate-limit respect and retry."""
        page = 1
        per_page = 100
        all_items: list[dict[str, Any]] = []
        query = dict(params or {})
        query["per_page"] = str(per_page)

        while True:
            query["page"] = str(page)
            resp = await self._request_with_retry(client, "GET", path, params=query)
            if resp.status_code != 200:
                break
            items = resp.json()
            if not items:
                break
            all_items.extend(items)
            if len(items) < per_page:
                break
            page += 1

        return all_items

    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Exponential backoff on 5xx; fail fast on 401/403."""
        import asyncio
        import time

        max_retries = 3
        for attempt in range(max_retries):
            resp = await client.request(method, path, params=params)

            # Fail fast on auth errors
            if resp.status_code in (401, 403):
                raise RuntimeError(f"GitHub auth error {resp.status_code}: {resp.text}")

            # Rate limit handling
            remaining = resp.headers.get("X-RateLimit-Remaining")
            if remaining and int(remaining) == 0:
                if attempt >= max_retries - 1:
                    raise RuntimeError(
                        f"GitHub rate limit exhausted after {max_retries} attempts"
                    )
                reset_at = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait = max(0, reset_at - int(time.time()))
                await asyncio.sleep(wait + 1)
                continue

            if resp.status_code >= 500:
                if attempt < max_retries - 1:
                    delay = 2 ** attempt
                    await asyncio.sleep(delay)
                    continue
                raise RuntimeError(f"GitHub server error {resp.status_code} after retries")

            return resp

        return resp  # type: ignore[return-value]

    async def _get_filtered_pr_stats(
        self, client: httpx.AsyncClient, repo: str, pr_number: int
    ) -> tuple[int, int]:
        """Get PR file-level diff stats, excluding linguist-generated/vendored files.

        In v1 we filter by checking filename patterns that commonly match
        linguist-generated files. A future v2 enhancement could fetch .gitattributes.
        """
        files = await self._paginate(client, f"/repos/{repo}/pulls/{pr_number}/files")
        filtered_adds = 0
        filtered_dels = 0
        for f in files:
            filename: str = f.get("filename", "")
            if _is_linguist_generated(filename):
                continue
            filtered_adds += f.get("additions", 0)
            filtered_dels += f.get("deletions", 0)
        return filtered_adds, filtered_dels


def _is_linguist_generated(filename: str) -> bool:
    """Heuristic for linguist-generated files (v1 approximation)."""
    generated_patterns = (
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Gemfile.lock",
        "Podfile.lock",
        "composer.lock",
        ".lock",
        "vendor/",
        "node_modules/",
        "dist/",
        "build/",
        ".min.js",
        ".min.css",
        "generated/",
        "generated.",
    )
    return any(pat in filename for pat in generated_patterns)
