"""Aggregation query implementations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from project_health.aggregation.core import (
    Timeframe,
    classify_pr_size,
    get_bot_set,
    issue_completed_sql,
    issue_open_sql,
    normalize_issue_type,
    resolve_bucket_size,
)
from project_health.config.loader import Config
from project_health.providers.protocol import sources_for_event_type

UTC = UTC


class WorkItemMetadata(BaseModel):
    additions: int | None = None
    deletions: int | None = None
    reviewers: list[str] | None = None
    issue_type: str | None = None
    story_points: int | None = None
    labels: list[str] | None = None
    pr_number: int | None = None
    sha: str | None = None


class WorkItem(BaseModel):
    id: str
    datasource: str
    event_type: str
    external_id: str
    project: str
    title: str
    description: str | None = None
    status: str
    timestamp: datetime
    url: str
    metadata: WorkItemMetadata | None = None


class CommitItem(BaseModel):
    id: str
    sha: str
    message: str
    timestamp: datetime
    url: str
    project: str
    pr_number: int | None = None


class WorkItemsResponse(BaseModel):
    person_id: str
    status: str
    total: int
    page: int
    per_page: int
    items: list[WorkItem]


class CommitsResponse(BaseModel):
    person_id: str
    total: int
    page: int
    per_page: int
    items: list[CommitItem]


JIRA_TERMINAL_STATES = {"done", "closed", "cancelled", "resolved", "completed"}
GITHUB_PR_ACTIVE_STATES = {"open"}
GITHUB_ISSUE_ACTIVE_STATES = {"open"}


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def _percentile(data: list[float], p: float) -> float | None:
    if not data:
        return None
    s = sorted(data)
    k = (len(s) - 1) * p
    f = int(k)
    c = f + 1
    if c >= len(s):
        return s[-1]
    return s[f] + (s[c] - s[f]) * (k - f)


def _median(data: list[float]) -> float | None:
    return _percentile(data, 0.5)


class AggregationQueries:
    """Execute aggregation queries against raw_events."""

    def __init__(
        self,
        session: AsyncSession,
        config: Config,
        configured_sources: set[str] | None = None,
    ) -> None:
        self._session = session
        self._config = config
        self._bots = get_bot_set(config)
        self._configured_sources = configured_sources or {"github", "jira"}

    def _source_filter(
        self,
        event_type: str,
        alias: str = "",
        configured_sources: set[str] | None = None,
    ) -> tuple[str, dict[str, str]]:
        sources = sources_for_event_type(
            event_type, configured_sources or self._configured_sources
        )
        if not sources:
            return "AND 1=0", {}
        col = f"{alias}.source" if alias else "source"
        params = {f"src_{i}": s for i, s in enumerate(sorted(sources))}
        placeholders = ", ".join(f":src_{i}" for i in range(len(sources)))
        return f"AND {col} IN ({placeholders})", params

    async def contribution_volume(self, ctx: Timeframe) -> dict[str, Any]:
        bot_filter, bot_params = self._bot_filter()
        proj_clause, proj_params = self._project_filter(ctx)
        actor_clause, actor_params = self._actor_filter(ctx)

        commit_src, commit_src_params = self._source_filter("commit")
        base_params = {
            "start": ctx.start, "end": ctx.end,
            **bot_params, **proj_params, **actor_params, **commit_src_params,
        }
        commits_sql = f"""
            SELECT COUNT(*) as cnt FROM raw_events
            WHERE event_type = 'commit'
            {commit_src}
            AND timestamp BETWEEN :start AND :end
            {bot_filter} {proj_clause} {actor_clause}
        """
        commits_result = await self._session.execute(text(commits_sql), base_params)
        commits = commits_result.scalar() or 0

        pr_src, pr_src_params = self._source_filter("pull_request")
        base_params.update(pr_src_params)
        prs_sql = f"""
            SELECT COUNT(*) as cnt,
                   COALESCE(SUM(CAST(json_extract(data, '$.additions') AS INTEGER)), 0) as adds,
                   COALESCE(SUM(CAST(json_extract(data, '$.deletions') AS INTEGER)), 0) as dels
            FROM raw_events
            WHERE event_type = 'pull_request'
            {pr_src}
            AND timestamp BETWEEN :start AND :end
            AND json_extract(data, '$.merged_at') IS NOT NULL
            {bot_filter} {proj_clause} {actor_clause}
        """
        prs_result = await self._session.execute(text(prs_sql), base_params)
        pr_row = prs_result.mappings().fetchone()
        pr_count = pr_row["cnt"] if pr_row else 0
        additions = pr_row["adds"] if pr_row else 0
        deletions = pr_row["dels"] if pr_row else 0

        issue_src, issue_src_params = self._source_filter("issue")
        base_params.update(issue_src_params)
        issues_open_sql = f"""
            SELECT COUNT(*) as cnt FROM raw_events
            WHERE event_type = 'issue'
            {issue_src}
            AND timestamp BETWEEN :start AND :end
            {bot_filter} {proj_clause} {actor_clause}
        """
        issues_open_result = await self._session.execute(text(issues_open_sql), base_params)
        issues_opened = issues_open_result.scalar() or 0

        issues_resolved_sql = f"""
            SELECT COUNT(*) as cnt FROM raw_events
            WHERE event_type = 'issue'
            {issue_src}
            AND timestamp BETWEEN :start AND :end
            AND {issue_completed_sql()}
            {bot_filter} {proj_clause} {actor_clause}
        """
        issues_resolved_result = await self._session.execute(text(issues_resolved_sql), base_params)
        issues_resolved = issues_resolved_result.scalar() or 0

        internal_sql = f"""
            SELECT COUNT(*) as cnt FROM raw_events
            WHERE event_type = 'pull_request'
            {pr_src}
            AND timestamp BETWEEN :start AND :end
            AND json_extract(data, '$.merged_at') IS NOT NULL
            AND actor IN (
                SELECT pi.external_id FROM person_identities pi
                JOIN persons p ON pi.person_id = p.id
                WHERE pi.source IN ({', '.join(f':src_{i}' for i in range(len(pr_src_params)))})
            )
            {proj_clause} {actor_clause}
        """
        internal_result = await self._session.execute(text(internal_sql), base_params)
        internal_prs = internal_result.scalar() or 0
        ratio = internal_prs / pr_count if pr_count > 0 else 0.0

        return {
            "commits": commits,
            "pull_requests": pr_count,
            "change_requests": pr_count,
            "additions": additions,
            "deletions": deletions,
            "issues_opened": issues_opened,
            "issues_resolved": issues_resolved,
            "internal_ratio": ratio,
            "external_ratio": 1.0 - ratio,
            "per_source": await self._contribution_volume_per_source(ctx),
        }

    async def _contribution_volume_per_source(self, ctx: Timeframe) -> dict[str, dict[str, Any]]:
        bot_filter, bot_params = self._bot_filter()
        proj_clause, proj_params = self._project_filter(ctx)
        actor_clause, actor_params = self._actor_filter(ctx)
        sql = f"""
            SELECT
                source,
                COUNT(CASE WHEN event_type = 'commit' THEN 1 END) as commits,
                COUNT(CASE WHEN event_type = 'pull_request' AND json_extract(data, '$.merged_at') IS NOT NULL THEN 1 END) as change_requests,
                COUNT(CASE WHEN event_type = 'issue' THEN 1 END) as issues_opened,
                COUNT(CASE WHEN event_type = 'issue' AND {issue_completed_sql()} THEN 1 END) as issues_resolved,
                COUNT(CASE WHEN event_type = 'review_decision' THEN 1 END) as review_decisions,
                COUNT(CASE WHEN event_type = 'review_comment' THEN 1 END) as review_comments
            FROM raw_events
            WHERE timestamp BETWEEN :start AND :end
            {bot_filter} {proj_clause} {actor_clause}
            GROUP BY source
        """
        result = await self._session.execute(
            text(sql),
            {"start": ctx.start, "end": ctx.end, **bot_params, **proj_params, **actor_params},
        )
        per_source: dict[str, dict[str, Any]] = {}
        for row in result.mappings().all():
            label = "Merge Proposals" if row["source"] == "launchpad" else "Pull Requests"
            per_source[row["source"]] = {
                "commits": row["commits"] or 0,
                "pull_requests": row["change_requests"] or 0,
                "change_requests": row["change_requests"] or 0,
                "change_request_label": label,
                "issues_opened": row["issues_opened"] or 0,
                "issues_resolved": row["issues_resolved"] or 0,
                "review_decisions": row["review_decisions"] or 0,
                "review_comments": row["review_comments"] or 0,
            }
        return per_source

    async def velocity(self, ctx: Timeframe) -> dict[str, Any]:
        proj_clause, proj_params = self._project_filter(ctx)
        actor_clause, actor_params = self._actor_filter(ctx)
        pr_src, pr_src_params = self._source_filter("pull_request")
        base_params = {"start": ctx.start, "end": ctx.end, **proj_params, **actor_params, **pr_src_params}

        cycle_sql = f"""
            SELECT
                timestamp as created_at,
                json_extract(data, '$.merged_at') as merged_at
            FROM raw_events
            WHERE event_type = 'pull_request'
            {pr_src}
            AND timestamp BETWEEN :start AND :end
            AND json_extract(data, '$.merged_at') IS NOT NULL
            {proj_clause} {actor_clause}
        """
        cycle_result = await self._session.execute(text(cycle_sql), base_params)

        cycle_times = []
        for row in cycle_result.mappings().all():
            created = row["created_at"]
            merged = row["merged_at"]
            if created and merged:
                try:
                    c_dt = _parse_dt(created)
                    m_dt = _parse_dt(merged)
                    if c_dt is None or m_dt is None:
                        continue
                    hours = (m_dt - c_dt).total_seconds() / 3600
                    if hours > 0:
                        cycle_times.append(hours)
                except Exception:
                    pass

        review_proj_clause, _ = self._project_filter(ctx, alias="pr")
        review_src, review_src_params = self._source_filter("review_decision", alias="r")
        pr_src2, pr_src_params2 = self._source_filter("pull_request", alias="pr")
        base_params.update({**review_src_params, **pr_src_params2})
        review_sql = f"""
            SELECT
                pr.timestamp as pr_created_at,
                MIN(r.timestamp) as first_review
            FROM raw_events pr
            JOIN raw_events r ON (
                r.event_type = 'review_decision'
                {review_src}
                AND r.source = pr.source
                AND COALESCE(json_extract(r.data, '$.pr_external_id'), json_extract(r.data, '$.change_request_external_id')) = pr.external_id
                AND r.actor != pr.actor
            )
            WHERE pr.event_type = 'pull_request'
            {pr_src2}
            AND pr.timestamp BETWEEN :start AND :end
            {review_proj_clause}
            GROUP BY pr.external_id
        """
        review_result = await self._session.execute(text(review_sql), base_params)
        review_turnarounds = []
        for row in review_result.mappings().all():
            c_dt = _parse_dt(row["pr_created_at"])
            r_dt = _parse_dt(row["first_review"])
            if c_dt is None or r_dt is None:
                continue
            try:
                hours = (r_dt - c_dt).total_seconds() / 3600
                if hours > 0:
                    review_turnarounds.append(hours)
            except Exception:
                pass

        return {
            "cycle_time_median": _median(cycle_times),
            "cycle_time_p50": _median(cycle_times),
            "cycle_time_p90": _percentile(cycle_times, 0.9),
            "review_turnaround_median": _median(review_turnarounds),
            "review_turnaround_p50": _median(review_turnarounds),
            "review_turnaround_p90": _percentile(review_turnarounds, 0.9),
            "per_source": {"github": {"cycle_time_count": len(cycle_times)}},
        }

    async def composition(self, ctx: Timeframe) -> dict[str, Any]:
        proj_clause, proj_params = self._project_filter(ctx)
        actor_clause, actor_params = self._actor_filter(ctx)
        issue_src, issue_src_params = self._source_filter("issue")
        base_params = {"start": ctx.start, "end": ctx.end, **proj_params, **actor_params, **issue_src_params}

        issue_sql = f"""
            SELECT data, source FROM raw_events
            WHERE event_type = 'issue'
            {issue_src}
            AND timestamp BETWEEN :start AND :end
            {proj_clause} {actor_clause}
        """
        issue_result = await self._session.execute(text(issue_sql), base_params)
        issue_types: dict[str, int] = {}
        for row in issue_result.mappings().all():
            data = row["data"]
            source = row["source"]
            if isinstance(data, str):
                data = json.loads(data)
            labels = data.get("labels") or ["other"]
            raw_type = data.get("issue_type") or labels[0]
            normalized = normalize_issue_type(source, raw_type, self._config)
            issue_types[normalized] = issue_types.get(normalized, 0) + 1

        pr_src, pr_src_params = self._source_filter("pull_request")
        base_params.update(pr_src_params)
        pr_sql = f"""
            SELECT data, source FROM raw_events
            WHERE event_type = 'pull_request'
            {pr_src}
            AND timestamp BETWEEN :start AND :end
            AND json_extract(data, '$.merged_at') IS NOT NULL
            {proj_clause} {actor_clause}
        """
        pr_result = await self._session.execute(text(pr_sql), base_params)
        pr_sizes: dict[str, int] = {"small": 0, "medium": 0, "large": 0}
        unclassified = 0
        for row in pr_result.mappings().all():
            data = row["data"]
            if isinstance(data, str):
                data = json.loads(data)
            filtered_adds = data.get("linguist_filtered_additions")
            filtered_dels = data.get("linguist_filtered_deletions")
            if filtered_adds is None and filtered_dels is None:
                unclassified += 1
                continue
            size = classify_pr_size(filtered_adds or 0, filtered_dels or 0)
            pr_sizes[size] = pr_sizes.get(size, 0) + 1

        return {
            "issue_types": issue_types,
            "pr_sizes": pr_sizes,
            "unclassified_change_requests": unclassified,
            "per_source": {},
        }

    async def collaboration(self, ctx: Timeframe) -> dict[str, Any]:
        proj_clause, proj_params = self._project_filter(ctx)
        actor_clause, actor_params = self._actor_filter(ctx)
        params = {"start": ctx.start, "end": ctx.end, **proj_params, **actor_params}

        review_proj_clause, _ = self._project_filter(ctx, alias="r")
        review_actor_clause, _ = self._actor_filter(ctx, alias="r")
        review_src, review_src_params = self._source_filter("review_decision", alias="r")
        pr_src, pr_src_params = self._source_filter("pull_request", alias="pr")
        params.update({**review_src_params, **pr_src_params})

        review_sql = f"""
            SELECT
                r.actor AS reviewer,
                pr.actor AS author,
                COALESCE(json_extract(r.data, '$.normalized_state'), json_extract(r.data, '$.review_state')) AS review_state,
                COALESCE(CAST(json_extract(r.data, '$.comment_count') AS INTEGER), 0) AS comment_count
            FROM raw_events r
            JOIN raw_events pr ON (
                pr.event_type = 'pull_request'
                {pr_src}
                AND r.source = pr.source
                AND pr.external_id = COALESCE(json_extract(r.data, '$.pr_external_id'), json_extract(r.data, '$.change_request_external_id'))
            )
            WHERE r.event_type = 'review_decision'
            {review_src}
            AND r.timestamp BETWEEN :start AND :end
            AND r.actor != pr.actor
            {review_proj_clause} {review_actor_clause}
        """
        result = await self._session.execute(text(review_sql), params)
        rows = result.mappings().all()

        matrix: dict[str, dict[str, int]] = {}
        per_person: dict[str, dict[str, Any]] = {}

        for row in rows:
            reviewer = row["reviewer"]
            author = row["author"]
            if not reviewer or not author:
                continue
            matrix.setdefault(reviewer, {}).setdefault(author, 0)
            matrix[reviewer][author] += 1
            stats = per_person.setdefault(reviewer, {"reviews": 0, "comments": 0})
            stats["reviews"] += 1
            stats["comments"] += row["comment_count"]

        return {"review_matrix": matrix, "per_person": per_person}

    async def sprint_burndown(self, sprint_id: str) -> dict[str, Any]:
        sprint_sql = """
            SELECT start_date, end_date FROM sprints WHERE id = :sprint_id
        """
        sprint_result = await self._session.execute(text(sprint_sql), {"sprint_id": sprint_id})
        sprint_row = sprint_result.mappings().fetchone()
        if not sprint_row:
            return {"committed": 0, "completed": 0, "carried_over": 0, "unit": "issues"}

        start = sprint_row["start_date"]
        end = sprint_row["end_date"]

        issue_sql = """
            SELECT data FROM raw_events
            WHERE event_type = 'issue' AND source = 'jira'
            AND timestamp BETWEEN :start AND :end
        """
        issue_result = await self._session.execute(text(issue_sql), {"start": start, "end": end})
        total_sp = 0.0
        completed_sp = 0.0
        total_issues = 0
        completed_issues = 0
        has_story_points = False

        for row in issue_result.mappings().all():
            data = row["data"]
            if isinstance(data, str):
                data = json.loads(data)
            sp = data.get("story_points")
            status = data.get("status", "").lower()
            if sp is not None:
                has_story_points = True
                total_sp += float(sp)
                if status in ("done", "closed", "resolved", "completed"):
                    completed_sp += float(sp)
            total_issues += 1
            if status in ("done", "closed", "resolved", "completed"):
                completed_issues += 1

        if has_story_points:
            return {
                "committed": total_sp,
                "completed": completed_sp,
                "carried_over": max(total_sp - completed_sp, 0),
                "unit": "story_points",
            }
        return {
            "committed": total_issues,
            "completed": completed_issues,
            "carried_over": max(total_issues - completed_issues, 0),
            "unit": "issues",
        }

    async def list_persons(self, ctx: Timeframe) -> list[dict[str, Any]]:
        bot_filter, bot_params = self._bot_filter()
        proj_clause, proj_params = self._project_filter(ctx)

        sql = """
            SELECT
                p.id as person_id,
                p.display_name,
                pi.source,
                pi.external_id,
                pi.display_name as identity_display_name,
                pi.profile_url
            FROM persons p
            LEFT JOIN person_identities pi ON pi.person_id = p.id
            WHERE p.active = 1
            ORDER BY p.display_name
        """
        result = await self._session.execute(text(sql))
        rows = result.mappings().all()

        persons_map: dict[str, dict[str, Any]] = {}
        for row in rows:
            pid = row["person_id"]
            if pid not in persons_map:
                persons_map[pid] = {
                    "id": pid,
                    "display_name": row["display_name"],
                    "identities": [],
                }
            if row["source"] and row["external_id"]:
                persons_map[pid]["identities"].append({
                    "source": row["source"],
                    "external_id": row["external_id"],
                    "display_name": row["identity_display_name"],
                    "profile_url": row["profile_url"],
                })

        persons = list(persons_map.values())
        for person in persons:
            identity_pairs = [
                (id_info["source"], id_info["external_id"])
                for id_info in person["identities"]
            ]
            if not identity_pairs:
                person["metrics"] = self._empty_person_metrics()
                continue
            metrics = await self._person_metrics(ctx, identity_pairs, bot_filter, bot_params, proj_clause, proj_params)
            person["metrics"] = metrics

        return persons

    async def person_contributions(self, person_id: str, ctx: Timeframe) -> dict[str, Any] | None:
        id_sql = """
            SELECT p.id, p.display_name, pi.source, pi.external_id, pi.display_name as identity_display_name, pi.profile_url
            FROM persons p
            LEFT JOIN person_identities pi ON pi.person_id = p.id
            WHERE p.id = :person_id AND p.active = 1
        """
        id_result = await self._session.execute(text(id_sql), {"person_id": person_id})
        id_rows = id_result.mappings().all()
        if not id_rows:
            return None

        display_name = id_rows[0]["display_name"]
        identities = [
            {
                "source": row["source"],
                "external_id": row["external_id"],
                "display_name": row["identity_display_name"],
                "profile_url": row["profile_url"],
            }
            for row in id_rows if row["source"] and row["external_id"]
        ]

        bot_filter, bot_params = self._bot_filter()
        proj_clause, proj_params = self._project_filter(ctx)

        contributions = await self._person_detail_contributions(
            ctx, identities, bot_filter, bot_params, proj_clause, proj_params
        )

        return {
            "person_id": person_id,
            "display_name": display_name,
            "identities": identities,
            "timeframe": {"kind": ctx.kind, "start": ctx.start.isoformat(), "end": ctx.end.isoformat()},
            "contributions": contributions,
        }

    async def _person_detail_contributions(
        self,
        ctx: Timeframe,
        identities: list[dict[str, Any]],
        bot_filter: str,
        bot_params: dict[str, str],
        proj_clause: str,
        proj_params: dict[str, str],
    ) -> list[dict[str, Any]]:
        if not identities:
            return []

        pair_params: dict[str, str] = {}
        pair_clauses: list[str] = []
        for i, (id_info) in enumerate(identities):
            pair_params[f"ids_{i}"] = id_info["source"]
            pair_params[f"idx_{i}"] = id_info["external_id"]
            pair_clauses.append(f"(:ids_{i}, :idx_{i})")

        identity_pairs_sql = ", ".join(pair_clauses)

        sql = f"""
            SELECT
                source,
                event_type,
                project,
                COUNT(*) as cnt,
                COALESCE(SUM(CASE WHEN event_type = 'pull_request' AND json_extract(data, '$.merged_at') IS NOT NULL
                    THEN CAST(json_extract(data, '$.additions') AS INTEGER) END), 0) as adds,
                COALESCE(SUM(CASE WHEN event_type = 'pull_request' AND json_extract(data, '$.merged_at') IS NOT NULL
                    THEN CAST(json_extract(data, '$.deletions') AS INTEGER) END), 0) as dels,
                COALESCE(SUM(CASE WHEN event_type = 'issue' AND {issue_completed_sql()}
                    THEN 1 END), 0) as issues_resolved,
                COALESCE(SUM(CASE WHEN event_type = 'issue' AND {issue_open_sql()}
                    THEN 1 END), 0) as issues_opened
            FROM raw_events
            WHERE (source, actor) IN ({identity_pairs_sql})
            AND timestamp BETWEEN :start AND :end
            {bot_filter} {proj_clause}
            GROUP BY source, event_type, project
        """
        params = {"start": ctx.start, "end": ctx.end, **bot_params, **proj_params, **pair_params}
        result = await self._session.execute(text(sql), params)
        rows = result.mappings().all()

        datasource_data: dict[str, dict[str, Any]] = {}
        for row in rows:
            source = row["source"]
            project = row["project"] or "unknown"
            if source not in datasource_data:
                datasource_data[source] = {"projects": {}}
            ds = datasource_data[source]
            if project not in ds["projects"]:
                ds["projects"][project] = {
                    "commits": 0,
                    "pull_requests": 0,
                    "pr_loc_added": 0,
                    "pr_loc_removed": 0,
                    "issues_resolved": 0,
                    "issues_opened": 0,
                    "reviews_given": 0,
                    "review_comments": 0,
                }
            proj_data = ds["projects"][project]
            if row["event_type"] == "commit":
                proj_data["commits"] = row["cnt"]
            elif row["event_type"] == "pull_request":
                proj_data["pull_requests"] = row["cnt"]
                proj_data["pr_loc_added"] = row["adds"]
                proj_data["pr_loc_removed"] = row["dels"]
            elif row["event_type"] == "review_decision":
                proj_data["reviews_given"] = row["cnt"]
            elif row["event_type"] == "review_comment":
                proj_data["review_comments"] = row["cnt"]
            elif row["event_type"] == "issue":
                proj_data["issues_resolved"] = row["issues_resolved"]
                proj_data["issues_opened"] = row["issues_opened"]

        from project_health.providers.protocol import DatasourceRole

        contributions = []
        for source, data in datasource_data.items():
            role = DatasourceRole.UMBRELLA if source == "jira" else DatasourceRole.CODE
            projects_list = []
            for proj_name, proj_metrics in data["projects"].items():
                projects_list.append({"project": proj_name, **proj_metrics})
            contributions.append({
                "datasource": source,
                "role": role.value,
                "projects": projects_list,
            })

        return contributions

    async def _person_metrics(
        self,
        ctx: Timeframe,
        identity_pairs: list[tuple[str, str]],
        bot_filter: str,
        bot_params: dict[str, str],
        proj_clause: str,
        proj_params: dict[str, str],
    ) -> dict[str, Any]:
        pair_params: dict[str, str] = {}
        pair_clauses: list[str] = []
        for i, (source, ext_id) in enumerate(identity_pairs):
            pair_params[f"ids_{i}"] = source
            pair_params[f"idx_{i}"] = ext_id
            pair_clauses.append(f"(:ids_{i}, :idx_{i})")
        identity_pairs_sql = ", ".join(pair_clauses)

        sql = f"""
            SELECT
                event_type,
                source,
                COUNT(*) as cnt,
                COALESCE(SUM(CASE WHEN event_type = 'pull_request' AND json_extract(data, '$.merged_at') IS NOT NULL
                    THEN 1 END), 0) as prs_merged,
                COALESCE(SUM(CASE WHEN event_type = 'pull_request' AND json_extract(data, '$.merged_at') IS NOT NULL
                    THEN CAST(json_extract(data, '$.additions') AS INTEGER) END), 0) as adds,
                COALESCE(SUM(CASE WHEN event_type = 'pull_request' AND json_extract(data, '$.merged_at') IS NOT NULL
                    THEN CAST(json_extract(data, '$.deletions') AS INTEGER) END), 0) as dels,
                COALESCE(SUM(CASE WHEN event_type = 'issue' AND {issue_completed_sql()}
                    THEN 1 END), 0) as issues_resolved,
                COALESCE(SUM(CASE WHEN event_type = 'issue' AND {issue_open_sql()}
                    THEN 1 END), 0) as issues_opened
            FROM raw_events
            WHERE (source, actor) IN ({identity_pairs_sql})
            AND timestamp BETWEEN :start AND :end
            {bot_filter} {proj_clause}
            GROUP BY event_type, source
        """
        all_params = {"start": ctx.start, "end": ctx.end, **bot_params, **proj_params, **pair_params}
        result = await self._session.execute(text(sql), all_params)
        rows = result.mappings().all()

        metrics = self._empty_person_metrics()
        for row in rows:
            et = row["event_type"]
            source = row["source"]
            if source not in metrics["sources"]:
                metrics["sources"][source] = {}
            src_metrics = metrics["sources"][source]

            if et == "commit":
                metrics["commits"] += row["cnt"]
                src_metrics["commits"] = row["cnt"]
            elif et == "pull_request":
                metrics["prs_opened"] += row["cnt"]
                prs_merged = row["prs_merged"]
                metrics["prs_merged"] += prs_merged
                metrics["pr_loc_added"] += row["adds"]
                metrics["pr_loc_removed"] += row["dels"]
                src_metrics["prs_merged"] = prs_merged
                src_metrics["pr_loc_added"] = row["adds"]
                src_metrics["pr_loc_removed"] = row["dels"]
            elif et == "review_decision":
                metrics["reviews_given"] += row["cnt"]
                src_metrics["reviews_given"] = row["cnt"]
            elif et == "review_comment":
                metrics["review_comments"] += row["cnt"]
                src_metrics["review_comments"] = row["cnt"]
            elif et == "issue":
                metrics["issues_resolved"] += row["issues_resolved"]
                metrics["issues_opened"] += row["issues_opened"]
                src_metrics["issues_resolved"] = row["issues_resolved"]
                src_metrics["issues_opened"] = row["issues_opened"]

        cycle_sql = f"""
            SELECT
                timestamp as created_at,
                json_extract(data, '$.merged_at') as merged_at
            FROM raw_events
            WHERE (source, actor) IN ({identity_pairs_sql})
            AND event_type = 'pull_request'
            AND timestamp BETWEEN :start AND :end
            AND json_extract(data, '$.merged_at') IS NOT NULL
            {proj_clause}
        """
        cycle_result = await self._session.execute(text(cycle_sql), all_params)
        cycle_times = []
        for row in cycle_result.mappings().all():
            c_dt = _parse_dt(row["created_at"])
            m_dt = _parse_dt(row["merged_at"])
            if c_dt and m_dt:
                hours = (m_dt - c_dt).total_seconds() / 3600
                if hours > 0:
                    cycle_times.append(hours)
        metrics["median_cycle_time_hours"] = _median(cycle_times)

        review_sql = f"""
            SELECT COUNT(*) as reviews,
                   COALESCE(SUM(CAST(json_extract(data, '$.comment_count') AS INTEGER)), 0) as comments
            FROM raw_events
            WHERE (source, actor) IN ({identity_pairs_sql})
            AND event_type IN ('review_decision', 'review_comment')
            AND timestamp BETWEEN :start AND :end
            {proj_clause}
        """
        review_result = await self._session.execute(text(review_sql), all_params)
        review_row = review_result.mappings().fetchone()
        if review_row:
            metrics["review_comments"] = metrics["review_comments"] or review_row["comments"] or 0

        return metrics

    def _empty_person_metrics(self) -> dict[str, Any]:
        return {
            "commits": 0,
            "prs_opened": 0,
            "prs_merged": 0,
            "pr_loc_added": 0,
            "pr_loc_removed": 0,
            "issues_resolved": 0,
            "issues_opened": 0,
            "reviews_given": 0,
            "review_comments": 0,
            "median_cycle_time_hours": None,
            "sources": {},
        }

    def _bucket_sql(self, ctx: Timeframe) -> tuple[str, str]:
        bucket = resolve_bucket_size(ctx.start, ctx.end)
        if bucket == "day":
            return ("strftime('%Y-%m-%d', timestamp)", "day")
        if bucket == "week":
            return ("strftime('%Y-%W', timestamp)", "week")
        if bucket == "month":
            return ("strftime('%Y-%m', timestamp)", "month")
        return ("strftime('%Y-%q', timestamp)", "quarter")

    async def contribution_volume_ts(self, ctx: Timeframe) -> dict[str, Any]:
        bucket_expr, bucket_size = self._bucket_sql(ctx)
        bot_filter, bot_params = self._bot_filter()
        proj_clause, proj_params = self._project_filter(ctx)
        actor_clause, actor_params = self._actor_filter(ctx)

        commit_sources = sources_for_event_type("commit", self._configured_sources)
        pr_sources = sources_for_event_type("pull_request", self._configured_sources)
        issue_sources = sources_for_event_type("issue", self._configured_sources)

        src_params: dict[str, str] = {}
        commit_placeholders = []
        for i, s in enumerate(sorted(commit_sources)):
            key = f"csrc_{i}"
            src_params[key] = s
            commit_placeholders.append(f":{key}")
        pr_placeholders = []
        for i, s in enumerate(sorted(pr_sources)):
            key = f"psrc_{i}"
            src_params[key] = s
            pr_placeholders.append(f":{key}")
        issue_placeholders = []
        for i, s in enumerate(sorted(issue_sources)):
            key = f"isrc_{i}"
            src_params[key] = s
            issue_placeholders.append(f":{key}")

        commit_in = ", ".join(commit_placeholders) if commit_placeholders else "'__none__'"
        pr_in = ", ".join(pr_placeholders) if pr_placeholders else "'__none__'"
        issue_in = ", ".join(issue_placeholders) if issue_placeholders else "'__none__'"

        base_params = {"start": ctx.start, "end": ctx.end, **bot_params, **proj_params, **actor_params, **src_params}

        sql = f"""
            SELECT
                {bucket_expr} as bucket,
                COUNT(CASE WHEN event_type = 'commit' AND source IN ({commit_in}) THEN 1 END) as commits,
                COUNT(CASE WHEN event_type = 'pull_request' AND source IN ({pr_in}) AND json_extract(data, '$.merged_at') IS NOT NULL THEN 1 END) as prs,
                COUNT(CASE WHEN event_type = 'issue' AND source IN ({issue_in}) THEN 1 END) as issues
            FROM raw_events
            WHERE timestamp BETWEEN :start AND :end
            {bot_filter} {proj_clause} {actor_clause}
            GROUP BY bucket
            ORDER BY bucket
        """
        result = await self._session.execute(text(sql), base_params)
        data = [
            {
                "bucket": row.bucket,
                "value": {"commits": row.commits, "prs": row.prs, "issues": row.issues},
            }
            for row in result.mappings().all()
        ]
        return {"bucket_size": bucket_size, "data": data}

    async def velocity_ts(self, ctx: Timeframe) -> dict[str, Any]:
        bucket_expr, bucket_size = self._bucket_sql(ctx)
        proj_clause, proj_params = self._project_filter(ctx)
        actor_clause, actor_params = self._actor_filter(ctx)
        pr_src, pr_src_params = self._source_filter("pull_request")
        base_params = {"start": ctx.start, "end": ctx.end, **proj_params, **actor_params, **pr_src_params}

        sql = f"""
            SELECT
                {bucket_expr} as bucket,
                AVG(
                    (julianday(json_extract(data, '$.merged_at')) - julianday(timestamp)) * 24
                ) as avg_cycle_hours
            FROM raw_events
            WHERE event_type = 'pull_request'
            {pr_src}
            AND timestamp BETWEEN :start AND :end
            AND json_extract(data, '$.merged_at') IS NOT NULL
            {proj_clause} {actor_clause}
            GROUP BY bucket
            ORDER BY bucket
        """
        result = await self._session.execute(text(sql), base_params)
        data = [
            {
                "bucket": row.bucket,
                "value": {
                    "avg_cycle_hours": round(row.avg_cycle_hours, 2)
                    if row.avg_cycle_hours
                    else None
                },
            }
            for row in result.mappings().all()
        ]
        return {"bucket_size": bucket_size, "data": data}

    async def collaboration_ts(self, ctx: Timeframe) -> dict[str, Any]:
        bucket_expr, bucket_size = self._bucket_sql(ctx)
        proj_clause, proj_params = self._project_filter(ctx)
        actor_clause, actor_params = self._actor_filter(ctx)
        review_src, review_src_params = self._source_filter("review_decision")
        base_params = {"start": ctx.start, "end": ctx.end, **proj_params, **actor_params, **review_src_params}

        sql = f"""
            SELECT
                {bucket_expr} as bucket,
                COUNT(*) as reviews
            FROM raw_events
            WHERE event_type = 'review_decision'
            {review_src}
            AND timestamp BETWEEN :start AND :end
            {proj_clause} {actor_clause}
            GROUP BY bucket
            ORDER BY bucket
        """
        result = await self._session.execute(text(sql), base_params)
        data = [
            {"bucket": row.bucket, "value": {"reviews": row.reviews}}
            for row in result.mappings().all()
        ]
        return {"bucket_size": bucket_size, "data": data}

    def _bot_filter(self) -> tuple[str, dict[str, str]]:
        if not self._bots:
            return "", {}
        params = {f"bot_{i}": b for i, b in enumerate(self._bots)}
        placeholders = ", ".join(f":bot_{i}" for i in range(len(self._bots)))
        return f"AND actor NOT IN ({placeholders})", params

    def _project_filter(self, ctx: Timeframe, alias: str = "") -> tuple[str, dict[str, str]]:
        if not ctx.projects:
            return "", {}
        col = f"{alias}.project" if alias else "project"
        params = {f"proj_{i}": p for i, p in enumerate(ctx.projects)}
        placeholders = ", ".join(f":proj_{i}" for i in range(len(ctx.projects)))
        return f"AND {col} IN ({placeholders})", params

    def _actor_filter(self, ctx: Timeframe, alias: str = "") -> tuple[str, dict[str, str]]:
        if not ctx.actors:
            return "", {}
        col = f"{alias}.actor" if alias else "actor"
        params = {f"actor_{i}": a for i, a in enumerate(ctx.actors)}
        placeholders = ", ".join(f":actor_{i}" for i in range(len(ctx.actors)))
        return f"AND {col} IN ({placeholders})", params

    async def work_items(
        self,
        person_id: str,
        status: Literal["active", "completed"],
        datasource: str | None,
        event_type: str | None,
        from_ts: datetime | None,
        to_ts: datetime | None,
        page: int,
        per_page: int,
    ) -> tuple[list[WorkItem], int]:
        id_sql = """
            SELECT source, external_id FROM person_identities
            WHERE person_id = :person_id
        """
        id_result = await self._session.execute(text(id_sql), {"person_id": person_id})
        id_rows = id_result.mappings().all()
        if not id_rows:
            return [], 0

        pair_params: dict[str, str] = {}
        pair_clauses: list[str] = []
        for i, row in enumerate(id_rows):
            pair_params[f"ids_{i}"] = row["source"]
            pair_params[f"idx_{i}"] = row["external_id"]
            pair_clauses.append(f"(:ids_{i}, :idx_{i})")
        identity_pairs_sql = ", ".join(pair_clauses)

        conditions = [f"(source, actor) IN ({identity_pairs_sql})"]
        params: dict[str, Any] = {**pair_params}

        if status == "active":
            conditions.append("event_type IN ('pull_request', 'issue')")
            conditions.append("""(
                (source = 'github' AND event_type = 'pull_request' AND json_extract(data, '$.state') = 'open')
                OR (source = 'github' AND event_type = 'issue' AND json_extract(data, '$.state') = 'open')
                OR (source = 'jira' AND event_type = 'issue' AND LOWER(json_extract(data, '$.status')) NOT IN ('done', 'closed', 'cancelled', 'resolved', 'completed'))
                OR (source = 'launchpad' AND event_type = 'pull_request' AND json_extract(data, '$.state') = 'open')
                OR (source = 'launchpad' AND event_type = 'issue' AND json_extract(data, '$.normalized_status') NOT IN ('done', 'cancelled'))
            )""")
        else:
            from_dt = from_ts or (datetime.now(UTC) - timedelta(days=30))
            to_dt = to_ts or datetime.now(UTC)
            conditions.append("timestamp BETWEEN :from_ts AND :to_ts")
            params["from_ts"] = from_dt
            params["to_ts"] = to_dt

        if datasource:
            conditions.append("source = :datasource")
            params["datasource"] = datasource

        if event_type:
            conditions.append("event_type = :event_type")
            params["event_type"] = event_type

        where_clause = " AND ".join(conditions)

        count_sql = f"SELECT COUNT(*) as cnt FROM raw_events WHERE {where_clause}"
        count_result = await self._session.execute(text(count_sql), params)
        total = count_result.scalar() or 0

        offset = (page - 1) * per_page
        data_sql = f"""
            SELECT id, source, event_type, external_id, project, timestamp, data
            FROM raw_events
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT :per_page OFFSET :offset
        """
        params["per_page"] = per_page
        params["offset"] = offset
        data_result = await self._session.execute(text(data_sql), params)

        items: list[WorkItem] = []
        for row in data_result.mappings().all():
            item = self._row_to_work_item(dict(row), status)
            if item:
                items.append(item)

        return items, total

    def _row_to_work_item(self, row: Mapping[str, Any], status: str) -> WorkItem | None:
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)

        source = row["source"]
        event_type = row["event_type"]
        external_id = str(row["external_id"])
        project = row["project"] or "unknown"
        timestamp = row["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

        title: str = ""
        description: str | None = None
        item_status: str = "unknown"
        url: str = ""
        metadata = WorkItemMetadata()

        if event_type == "pull_request":
            title = data.get("title", f"PR #{external_id}")
            description = data.get("body")
            pr_state = data.get("state", "unknown")
            merged_at = data.get("merged_at")
            if merged_at:
                item_status = "merged"
            elif pr_state == "closed":
                item_status = "closed"
            elif data.get("draft"):
                item_status = "draft"
            else:
                item_status = "open"
            url = data.get("html_url", "")
            metadata.additions = data.get("additions")
            metadata.deletions = data.get("deletions")
            reviewers = data.get("reviewers")
            if reviewers and isinstance(reviewers, list):
                metadata.reviewers = reviewers

        elif event_type == "issue":
            if source == "jira":
                title = data.get("summary", external_id)
                description = data.get("description")
                jira_status = (data.get("status") or "unknown").lower()
                if jira_status in JIRA_TERMINAL_STATES:
                    item_status = "Done"
                else:
                    item_status = data.get("status", "unknown")
                url = data.get("self", "")
                metadata.issue_type = data.get("issue_type")
                metadata.story_points = data.get("story_points")
                labels = data.get("labels")
                if labels and isinstance(labels, list):
                    metadata.labels = labels
            elif source == "launchpad":
                title = data.get("title", f"Bug {external_id}")
                description = data.get("description")
                item_status = data.get("normalized_status") or data.get("status", "unknown")
                url = data.get("html_url", "")
                metadata.issue_type = data.get("issue_type")
                labels = data.get("labels")
                if labels and isinstance(labels, list):
                    metadata.labels = labels
            else:
                title = data.get("title", f"Issue #{external_id}")
                description = data.get("body")
                issue_state = data.get("state", "unknown")
                item_status = "closed" if issue_state == "closed" else "open"
                url = data.get("html_url", "")
                labels = data.get("labels")
                if labels and isinstance(labels, list):
                    metadata.labels = labels

        elif event_type == "pull_request_review":
            title = f"Review on PR #{data.get('pr_external_id', external_id)}"
            description = data.get("body")
            item_status = data.get("review_state", "reviewed")
            pr_external_id = data.get("pr_external_id")
            metadata.pr_number = int(pr_external_id) if pr_external_id is not None else None
            url = data.get("html_url") or ""
            if not url and pr_external_id and project != "unknown":
                url = f"https://github.com/{project}/pull/{pr_external_id}#pullrequestreview-{external_id}"

        elif event_type == "commit":
            message = data.get("message", "")
            first_line = message.split("\n")[0] if message else f"Commit {external_id[:7]}"
            title = first_line[:80]
            description = message if "\n" in message else None
            item_status = "committed"
            url = data.get("html_url") or (f"https://github.com/{project}/commit/{external_id}" if project != "unknown" else "")
            metadata.sha = external_id[:7]
            metadata.pr_number = data.get("pr_number")

        else:
            title = f"{event_type} {external_id}"
            url = data.get("html_url", "")

        return WorkItem(
            id=str(row["id"]),
            datasource=source,
            event_type=event_type,
            external_id=external_id,
            project=project,
            title=title,
            description=description,
            status=item_status,
            timestamp=timestamp,
            url=url,
            metadata=metadata,
        )

    async def commits(
        self,
        person_id: str,
        from_ts: datetime | None,
        to_ts: datetime | None,
        page: int,
        per_page: int,
    ) -> tuple[list[CommitItem], int]:
        id_sql = """
            SELECT source, external_id FROM person_identities
            WHERE person_id = :person_id
        """
        id_result = await self._session.execute(text(id_sql), {"person_id": person_id})
        id_rows = id_result.mappings().all()
        if not id_rows:
            return [], 0

        pair_params: dict[str, str] = {}
        pair_clauses: list[str] = []
        for i, row in enumerate(id_rows):
            pair_params[f"ids_{i}"] = row["source"]
            pair_params[f"idx_{i}"] = row["external_id"]
            pair_clauses.append(f"(:ids_{i}, :idx_{i})")
        identity_pairs_sql = ", ".join(pair_clauses)

        conditions = [f"(source, actor) IN ({identity_pairs_sql})", "event_type = 'commit'"]
        params: dict[str, Any] = {**pair_params}

        if from_ts and to_ts:
            conditions.append("timestamp BETWEEN :from_ts AND :to_ts")
            params["from_ts"] = from_ts
            params["to_ts"] = to_ts

        where_clause = " AND ".join(conditions)

        count_sql = f"SELECT COUNT(*) as cnt FROM raw_events WHERE {where_clause}"
        count_result = await self._session.execute(text(count_sql), params)
        total = count_result.scalar() or 0

        offset = (page - 1) * per_page
        data_sql = f"""
            SELECT id, external_id, project, timestamp, data
            FROM raw_events
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT :per_page OFFSET :offset
        """
        params["per_page"] = per_page
        params["offset"] = offset
        data_result = await self._session.execute(text(data_sql), params)

        items: list[CommitItem] = []
        for row in data_result.mappings().all():
            data = row["data"]
            if isinstance(data, str):
                data = json.loads(data)

            sha = str(row["external_id"])[:7]
            full_sha = str(row["external_id"])
            message = data.get("message", "")
            timestamp = row["timestamp"]
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

            project = row["project"] or "unknown"
            url = data.get("html_url") or (f"https://github.com/{project}/commit/{full_sha}" if project != "unknown" else "")

            items.append(CommitItem(
                id=str(row["id"]),
                sha=sha,
                message=message[:100],
                timestamp=timestamp,
                url=url,
                project=project,
                pr_number=data.get("pr_number"),
            ))

        return items, total
