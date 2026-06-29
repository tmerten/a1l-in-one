"""Tests for Launchpad provider normalization."""

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from project_health.config.loader import Config, LaunchpadRepositoryConfig
from project_health.providers.launchpad import (
    LAUNCHPAD_API_ROOT,
    LaunchpadClient,
    LaunchpadProvider,
    _atom_commit_events,
    _bug_task_event,
    _default_ref_name,
    _merge_proposal_event,
    _review_comment_event,
    _review_decision_event,
    _vote_reference_event,
    normalize_launchpad_bug_status,
    normalize_launchpad_vote,
)
from project_health.providers.launchpad_oauth import LaunchpadOAuthCredentials


def test_launchpad_client_rejects_write_methods():
    client = LaunchpadClient()

    with pytest.raises(ValueError, match="GET and HEAD"):
        # Guard is enforced before any network IO.
        import asyncio

        asyncio.run(client.request("POST", "/bugs"))


def test_launchpad_client_uses_devel_api_root():
    client = LaunchpadClient()

    assert str(client._client.base_url) == LAUNCHPAD_API_ROOT + "/"


def test_launchpad_client_uses_oauth_signed_headers():
    client = LaunchpadClient(
        credentials=LaunchpadOAuthCredentials(
            consumer_key="project-health-dashboard",
            access_token="access-token",
            access_token_secret="access-secret",
        )
    )

    assert client._client.headers["Authorization"].startswith("OAuth ")
    assert 'oauth_token="access-token"' in client._client.headers["Authorization"]


@pytest.mark.asyncio
async def test_launchpad_bug_tasks_use_search_tasks_operation(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devel/maas":
            assert request.url.params["ws.op"] == "searchTasks"
            assert "modified_since" in request.url.params
            return httpx.Response(200, json={"entries": []})
        return httpx.Response(500)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.launchpad.net/devel",
    ) as http_client:
        monkeypatch.setattr(
            "project_health.providers.launchpad.httpx.AsyncClient",
            lambda *args, **kwargs: http_client,
        )
        client = LaunchpadClient()

        tasks = await client.bug_tasks("maas", datetime.now(UTC))

    assert tasks == []


def test_default_ref_name_uses_repository_default_branch():
    assert _default_ref_name({"default_branch": "refs/heads/main"}) == "main"
    assert _default_ref_name({"default_branch": "main"}) == "main"
    assert _default_ref_name({}) is None


@pytest.mark.asyncio
async def test_launchpad_commits_use_default_branch(monkeypatch):
    requests: list[httpx.Request] = []

    def api_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/devel/~team/project/+git/repo":
            return httpx.Response(
                200,
                json={
                    "default_branch": "refs/heads/main",
                    "git_https_url": "https://git.launchpad.net/~team/project/+git/repo",
                },
            )
        return httpx.Response(404)

    def git_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/~team/project/+git/repo/atom/":
            assert request.url.params["h"] == "main"
            return httpx.Response(
                200,
                text="""
                <feed xmlns='http://www.w3.org/2005/Atom'>
                  <entry>
                    <title>Commit message</title>
                    <updated>2026-06-20T10:00:00+00:00</updated>
                    <id>abc123</id>
                    <author><name>Alice</name></author>
                    <link rel='alternate' type='text/html' href='https://git.launchpad.net/repo/commit/?id=abc123'/>
                  </entry>
                </feed>
                """,
            )
        return httpx.Response(404)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(api_handler),
        base_url="https://api.launchpad.net/devel",
    ) as http_client, httpx.AsyncClient(
        transport=httpx.MockTransport(git_handler),
    ) as git_client:
        monkeypatch.setattr(
            "project_health.providers.launchpad.httpx.AsyncClient",
            lambda *args, **kwargs: http_client if "base_url" in kwargs else git_client,
        )
        client = LaunchpadClient()
        repo = LaunchpadRepositoryConfig.model_validate("~team/project/+git/repo")

        commits = await client.commits(repo, datetime(2026, 6, 1, tzinfo=UTC))

    assert commits[0]["sha1"] == "abc123"
    assert commits[0]["title"] == "Commit message"
    assert any(request.url.path.endswith("/atom/") for request in requests)
    assert not any(request.url.path.endswith("/+ref/master/commits") for request in requests)


@pytest.mark.asyncio
async def test_launchpad_commits_skip_missing_git_url(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devel/~team/project/+git/repo":
            return httpx.Response(200, json={"default_branch": "refs/heads/main"})
        return httpx.Response(500)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.launchpad.net/devel",
    ) as http_client:
        monkeypatch.setattr(
            "project_health.providers.launchpad.httpx.AsyncClient",
            lambda *args, **kwargs: http_client,
        )
        client = LaunchpadClient()
        repo = LaunchpadRepositoryConfig.model_validate("~team/project/+git/repo")

        commits = await client.commits(repo, datetime.now(UTC))

    assert commits == []


def test_atom_commit_events_filters_by_since():
    commits = _atom_commit_events(
        """
        <feed xmlns='http://www.w3.org/2005/Atom'>
          <entry>
            <title>New commit</title>
            <updated>2026-06-20T10:00:00+00:00</updated>
            <id>new-sha</id>
            <author><name>Alice</name></author>
          </entry>
          <entry>
            <title>Old commit</title>
            <updated>2026-05-01T10:00:00+00:00</updated>
            <id>old-sha</id>
            <author><name>Bob</name></author>
          </entry>
        </feed>
        """,
        datetime(2026, 6, 1, tzinfo=UTC),
    )

    assert [commit["sha1"] for commit in commits] == ["new-sha"]


@pytest.mark.asyncio
async def test_launchpad_merge_proposals_skip_missing_resource(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devel/~team/project/+git/repo":
            assert request.url.params["ws.op"] == "getMergeProposals"
            return httpx.Response(404)
        return httpx.Response(500)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.launchpad.net/devel",
    ) as http_client:
        monkeypatch.setattr(
            "project_health.providers.launchpad.httpx.AsyncClient",
            lambda *args, **kwargs: http_client,
        )
        client = LaunchpadClient()
        repo = LaunchpadRepositoryConfig.model_validate("~team/project/+git/repo")

        proposals = await client.merge_proposals(repo, datetime.now(UTC))

    assert proposals == []


@pytest.mark.asyncio
async def test_launchpad_review_subresources_skip_missing_resource(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path in {"/devel/mp/all_comments", "/devel/mp/votes"}:
            return httpx.Response(404)
        return httpx.Response(500)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.launchpad.net/devel",
    ) as http_client:
        monkeypatch.setattr(
            "project_health.providers.launchpad.httpx.AsyncClient",
            lambda *args, **kwargs: http_client,
        )
        client = LaunchpadClient()

        comments = await client.code_review_comments("/mp/all_comments")
        votes = await client.vote_references("/mp/votes")

    assert comments == []
    assert votes == []


def test_launchpad_bug_status_mapping():
    assert normalize_launchpad_bug_status("Fix Committed") == "done"
    assert normalize_launchpad_bug_status("Fix Released") == "done"
    assert normalize_launchpad_bug_status("Invalid") == "cancelled"
    assert normalize_launchpad_bug_status("Won't Fix") == "cancelled"
    assert normalize_launchpad_bug_status("Does Not Exist") == "cancelled"


def test_launchpad_bug_task_completion_credit():
    fixed = _bug_task_event("maas", {
        "id": "task-1",
        "bug": "123",
        "title": "Fixed bug",
        "status": "Fix Committed",
        "date_created": datetime.now(UTC).isoformat(),
        "assignee_link": "https://api.launchpad.net/devel/~alice",
        "owner_link": "https://api.launchpad.net/devel/~reporter",
    })
    invalid = _bug_task_event("maas", {
        "id": "task-2",
        "bug": "124",
        "title": "Invalid bug",
        "status": "Invalid",
        "date_created": datetime.now(UTC).isoformat(),
        "assignee_link": "https://api.launchpad.net/devel/~alice",
    })

    assert fixed is not None
    assert fixed.actor == "~alice"
    assert fixed.data["completed_contribution"] is True
    assert fixed.data["reporter"] == "~reporter"
    assert invalid is not None
    assert invalid.data["completed_contribution"] is False
    assert invalid.data["normalized_status"] == "cancelled"


def test_launchpad_merge_proposal_and_review_normalization():
    repo = LaunchpadRepositoryConfig.model_validate(
        "~maas-committers/maas/+git/maas-release-tools"
    )
    proposal = {
        "id": "mp-1",
        "date_created": datetime.now(UTC).isoformat(),
        "registrant_link": "https://api.launchpad.net/devel/~author",
        "queue_status": "Merged",
        "date_merged": datetime.now(UTC).isoformat(),
        "web_link": "https://code.launchpad.net/mp-1",
    }
    comment = {
        "id": "comment-1",
        "date_created": datetime.now(UTC).isoformat(),
        "owner_link": "https://api.launchpad.net/devel/~reviewer",
        "vote": "Needs Fixing",
        "content": "Please adjust this.",
    }
    vote = {
        "date_created": datetime.now(UTC).isoformat(),
        "reviewer_link": "https://api.launchpad.net/devel/~reviewer",
        "vote": "Needs Fixing",
    }

    mp_event = _merge_proposal_event(repo, proposal)
    decision_event = _review_decision_event(repo, proposal, comment)
    comment_event = _review_comment_event(repo, proposal, comment)
    request_event = _vote_reference_event(repo, proposal, vote)

    assert mp_event is not None
    assert mp_event.data["normalized_kind"] == "change_request"
    assert mp_event.data["state"] == "merged"
    assert decision_event is not None
    assert decision_event.data["normalized_state"] == "changes_requested"
    assert comment_event is not None
    assert comment_event.data["normalized_kind"] == "review_comment"
    assert request_event is not None
    assert request_event.actor == "~reviewer"
    assert normalize_launchpad_vote("Approve") == "approved"


@pytest.mark.asyncio
async def test_launchpad_review_comments_use_collection_link(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/devel/~team/project/+git/repo":
            return httpx.Response(
                200,
                json={
                    "entries": [
                        {
                            "id": "mp-1",
                            "date_created": datetime.now(UTC).isoformat(),
                            "registrant_link": "https://api.launchpad.net/devel/~author",
                            "all_comments_collection_link": "https://api.launchpad.net/devel/mp/all_comments",
                        }
                    ]
                },
            )
        if request.url.path == "/devel/mp/all_comments":
            return httpx.Response(
                200,
                json={
                    "entries": [
                        {
                            "id": "comment-1",
                            "date_created": datetime.now(UTC).isoformat(),
                            "owner_link": "https://api.launchpad.net/devel/~reviewer",
                            "content": "Looks good.",
                        }
                    ]
                },
            )
        return httpx.Response(500)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.launchpad.net/devel",
    ) as http_client:
        monkeypatch.setattr(
            "project_health.providers.launchpad.httpx.AsyncClient",
            lambda *args, **kwargs: http_client,
        )
        config = Config.model_validate(
            {
                "credentials": {"github_token": "token"},
                "launchpad-repos": ["~team/project/+git/repo"],
            }
        )
        provider = LaunchpadProvider(config)

        events = await provider.fetch_review_comments(datetime.now(UTC))

    assert len(events) == 1
    assert events[0].data["body"] == "Looks good."


def test_public_launchpad_cassette_shapes_normalize():
    cassette = json.loads(Path("tests/cassettes/launchpad_public.json").read_text())
    repo = LaunchpadRepositoryConfig.model_validate(cassette["repository"]["unique_name"])
    bug_task = cassette["bug_tasks"]["entries"][0]
    proposal = cassette["merge_proposals"]["entries"][0]
    vote = cassette["vote_references"]["entries"][0]
    comment = cassette["code_review_comments"]["entries"][0]

    bug_event = _bug_task_event("maas", bug_task)
    mp_event = _merge_proposal_event(repo, proposal)
    request_event = _vote_reference_event(repo, proposal, vote)
    decision_event = _review_decision_event(repo, proposal, comment)
    comment_event = _review_comment_event(repo, proposal, comment)

    assert cassette["repository"]["private"] is False
    assert cassette["refs"]["entries"][0]["commit_sha1"]
    assert bug_event is not None
    assert bug_event.data["completed_contribution"] is True
    assert mp_event is not None
    assert mp_event.data["capabilities"]["review_requests"] is True
    assert request_event is not None
    assert request_event.actor == "~team-devs"
    assert decision_event is not None
    assert decision_event.data["normalized_state"] == "approved"
    assert comment_event is not None
    assert comment_event.data["body"] == "Looks good."
    assert cassette["person"]["display_name"] == "Dana Dev"
    assert cassette["team"]["display_name"] == "Project Committers"
