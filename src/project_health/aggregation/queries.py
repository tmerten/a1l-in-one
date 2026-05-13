"""Aggregation query implementations."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from project_health.aggregation.core import (
    Timeframe,
    classify_pr_size,
    get_bot_set,
    normalize_issue_type,
    resolve_bucket_size,
)
from project_health.config.loader import Config


class AggregationQueries:
    """Execute aggregation queries against raw_events."""

    def __init__(self, session: AsyncSession, config: Config) -> None:
        self._session = session
        self._config = config
        self._bots = get_bot_set(config)

    # ------------------------------------------------------------------
    # 13.1–13.11 Metric Queries
    # ------------------------------------------------------------------

    async def contribution_volume(self, ctx: Timeframe) -> dict[str, Any]:
        """Commits, PRs, issues, internal/external ratio."""
        # Filter out bots and apply timeframe
        bot_list = ",".join(f"'{b}'" for b in self._bots)
        bot_filter = f"AND actor NOT IN ({bot_list})" if bot_list else ""
        proj_filter = self._project_filter(ctx)
        actor_filter = self._actor_filter(ctx)

        # Commits (event_type = commit)
        commits_sql = f"""
            SELECT COUNT(*) as cnt FROM raw_events
            WHERE source = 'github' AND event_type = 'commit'
            AND timestamp BETWEEN :start AND :end
            {bot_filter} {proj_filter} {actor_filter}
        """
        commits_result = await self._session.execute(
            text(commits_sql), {"start": ctx.start, "end": ctx.end}
        )
        commits = commits_result.scalar() or 0

        # PRs (merged only)
        prs_sql = f"""
            SELECT COUNT(*) as cnt,
                   COALESCE(SUM(CAST(json_extract(data, '$.additions') AS INTEGER)), 0) as adds,
                   COALESCE(SUM(CAST(json_extract(data, '$.deletions') AS INTEGER)), 0) as dels
            FROM raw_events
            WHERE source = 'github' AND event_type = 'pull_request'
            AND timestamp BETWEEN :start AND :end
            AND json_extract(data, '$.merged_at') IS NOT NULL
            {bot_filter} {proj_filter} {actor_filter}
        """
        prs_result = await self._session.execute(
            text(prs_sql), {"start": ctx.start, "end": ctx.end}
        )
        pr_row = prs_result.mappings().fetchone()
        pr_count = pr_row["cnt"] if pr_row else 0
        additions = pr_row["adds"] if pr_row else 0
        deletions = pr_row["dels"] if pr_row else 0

        # Issues opened
        issues_open_sql = f"""
            SELECT COUNT(*) as cnt FROM raw_events
            WHERE event_type = 'issue'
            AND timestamp BETWEEN :start AND :end
            {bot_filter} {proj_filter} {actor_filter}
        """
        issues_open_result = await self._session.execute(
            text(issues_open_sql), {"start": ctx.start, "end": ctx.end}
        )
        issues_opened = issues_open_result.scalar() or 0

        # Issues resolved (closed_at present)
        issues_resolved_sql = f"""
            SELECT COUNT(*) as cnt FROM raw_events
            WHERE event_type = 'issue'
            AND timestamp BETWEEN :start AND :end
            AND json_extract(data, '$.closed_at') IS NOT NULL
            {bot_filter} {proj_filter} {actor_filter}
        """
        issues_resolved_result = await self._session.execute(
            text(issues_resolved_sql), {"start": ctx.start, "end": ctx.end}
        )
        issues_resolved = issues_resolved_result.scalar() or 0

        # Internal / external ratio
        internal_sql = f"""
            SELECT COUNT(*) as cnt FROM raw_events
            WHERE source = 'github' AND event_type = 'pull_request'
            AND timestamp BETWEEN :start AND :end
            AND json_extract(data, '$.merged_at') IS NOT NULL
            AND actor IN (
                SELECT external_id FROM person_identities pi
                JOIN persons p ON pi.person_id = p.id
                WHERE pi.source = 'github'
            )
            {proj_filter} {actor_filter}
        """
        internal_result = await self._session.execute(
            text(internal_sql), {"start": ctx.start, "end": ctx.end}
        )
        internal_prs = internal_result.scalar() or 0
        ratio = internal_prs / pr_count if pr_count > 0 else 0.0

        return {
            "commits": commits,
            "pull_requests": pr_count,
            "additions": additions,
            "deletions": deletions,
            "issues_opened": issues_opened,
            "issues_resolved": issues_resolved,
            "internal_ratio": ratio,
            "external_ratio": 1.0 - ratio,
            "per_source": {
                "github": {
                    "commits": commits,
                    "pull_requests": pr_count,
                    "additions": additions,
                    "deletions": deletions,
                },
                "jira": {
                    "issues_opened": issues_opened - (0),  # approximate
                    "issues_resolved": issues_resolved - (0),
                },
            },
        }

    async def velocity(self, ctx: Timeframe) -> dict[str, Any]:
        """Cycle time and PR review turnaround distributions."""
        # Cycle times for merged PRs
        cycle_sql = """
            SELECT
                json_extract(data, '$.created_at') as created_at,
                json_extract(data, '$.merged_at') as merged_at
            FROM raw_events
            WHERE source = 'github' AND event_type = 'pull_request'
            AND timestamp BETWEEN :start AND :end
            AND json_extract(data, '$.merged_at') IS NOT NULL
        """
        cycle_result = await self._session.execute(
            text(cycle_sql), {"start": ctx.start, "end": ctx.end}
        )
        cycle_times = []
        for row in cycle_result.mappings().all():
            created = row["created_at"]
            merged = row["merged_at"]
            if created and merged:
                try:
                    c_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    m_dt = datetime.fromisoformat(merged.replace("Z", "+00:00"))
                    hours = (m_dt - c_dt).total_seconds() / 3600
                    if hours > 0:
                        cycle_times.append(hours)
                except Exception:
                    pass

        # Review turnaround: PR created_at to first review
        review_sql = """
            SELECT
                pr.data as pr_data,
                MIN(r.timestamp) as first_review
            FROM raw_events pr
            JOIN raw_events r ON (
                r.source = 'github'
                AND r.event_type = 'pull_request_review'
                AND json_extract(r.data, '$.pr_external_id') = pr.external_id
                AND r.actor != pr.actor
            )
            WHERE pr.source = 'github' AND pr.event_type = 'pull_request'
            AND pr.timestamp BETWEEN :start AND :end
            GROUP BY pr.external_id
        """
        review_result = await self._session.execute(
            text(review_sql), {"start": ctx.start, "end": ctx.end}
        )
        review_turnarounds = []
        for row in review_result.mappings().all():
            pr_data = json.loads(row["pr_data"]) if isinstance(row["pr_data"], str) else row["pr_data"]
            created_str = pr_data.get("created_at")
            first_review = row["first_review"]
            if created_str and first_review:
                try:
                    c_dt = datetime.fromisoformat(str(created_str).replace("Z", "+00:00"))
                    if isinstance(first_review, datetime):
                        r_dt = first_review
                    else:
                        r_dt = datetime.fromisoformat(str(first_review).replace("Z", "+00:00"))
                    hours = (r_dt - c_dt).total_seconds() / 3600
                    if hours > 0:
                        review_turnarounds.append(hours)
                except Exception:
                    pass

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
        """Issue type breakdown and PR size distribution."""
        # Issue types
        issue_sql = """
            SELECT data FROM raw_events
            WHERE event_type = 'issue'
            AND timestamp BETWEEN :start AND :end
        """
        issue_result = await self._session.execute(
            text(issue_sql), {"start": ctx.start, "end": ctx.end}
        )
        issue_types: dict[str, int] = {}
        for row in issue_result.mappings().all():
            data = row["data"]
            if isinstance(data, str):
                data = json.loads(data)
            raw_type = data.get("issue_type") or data.get("labels", ["other"])[0]
            source = "github" if "labels" in data else "jira"
            normalized = normalize_issue_type(source, raw_type, self._config)
            issue_types[normalized] = issue_types.get(normalized, 0) + 1

        # PR sizes
        pr_sql = """
            SELECT data FROM raw_events
            WHERE source = 'github' AND event_type = 'pull_request'
            AND timestamp BETWEEN :start AND :end
            AND json_extract(data, '$.merged_at') IS NOT NULL
        """
        pr_result = await self._session.execute(
            text(pr_sql), {"start": ctx.start, "end": ctx.end}
        )
        pr_sizes: dict[str, int] = {"small": 0, "medium": 0, "large": 0}
        for row in pr_result.mappings().all():
            data = row["data"]
            if isinstance(data, str):
                data = json.loads(data)
            filtered_adds = data.get("linguist_filtered_additions", 0) or 0
            filtered_dels = data.get("linguist_filtered_deletions", 0) or 0
            size = classify_pr_size(filtered_adds, filtered_dels)
            pr_sizes[size] = pr_sizes.get(size, 0) + 1

        return {
            "issue_types": issue_types,
            "pr_sizes": pr_sizes,
            "per_source": {},
        }

    async def collaboration(self, ctx: Timeframe) -> dict[str, Any]:
        """Review distribution matrix and per-person review activity."""
        review_sql = """
            SELECT actor, json_extract(data, '$.pr_external_id') as pr_id
            FROM raw_events
            WHERE source = 'github' AND event_type = 'pull_request_review'
            AND timestamp BETWEEN :start AND :end
        """
        review_result = await self._session.execute(
            text(review_sql), {"start": ctx.start, "end": ctx.end}
        )

        # reviewer -> author -> count
        matrix: dict[str, dict[str, int]] = {}
        # reviewer -> stats
        per_person: dict[str, dict[str, Any]] = {}

        for row in review_result.mappings().all():
            reviewer = row["actor"]
            pr_id = row["pr_id"]
            if not reviewer or not pr_id:
                continue
            # Find PR author
            pr_sql = """
                SELECT actor FROM raw_events
                WHERE source = 'github' AND event_type = 'pull_request'
                AND external_id = :pr_id
            """
            pr_result = await self._session.execute(text(pr_sql), {"pr_id": str(pr_id)})
            pr_row = pr_result.mappings().fetchone()
            author = pr_row["actor"] if pr_row else "unknown"
            if reviewer == author:
                continue
            matrix.setdefault(reviewer, {}).setdefault(author, 0)
            matrix[reviewer][author] += 1
            per_person.setdefault(reviewer, {"reviews": 0, "comments": 0})
            per_person[reviewer]["reviews"] += 1

        return {
            "review_matrix": matrix,
            "per_person": per_person,
        }

    async def sprint_burndown(self, sprint_id: str) -> dict[str, Any]:
        """Committed vs completed story points (or issue count fallback)."""
        # Find sprint date range
        sprint_sql = """
            SELECT start_date, end_date FROM sprints WHERE id = :sprint_id
        """
        sprint_result = await self._session.execute(text(sprint_sql), {"sprint_id": sprint_id})
        sprint_row = sprint_result.mappings().fetchone()
        if not sprint_row:
            return {"committed": 0, "completed": 0, "carried_over": 0, "unit": "issues"}

        start = sprint_row["start_date"]
        end = sprint_row["end_date"]

        # Get issues in sprint timeframe
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

    # ------------------------------------------------------------------
    # Time-series variants
    # ------------------------------------------------------------------

    def _bucket_sql(self, ctx: Timeframe) -> tuple[str, str]:
        """Return (bucket_expr, bucket_size) for SQLite strftime."""
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
        bot_list = ",".join(f"'{b}'" for b in self._bots)
        bot_filter = f"AND actor NOT IN ({bot_list})" if bot_list else ""

        sql = f"""
            SELECT
                {bucket_expr} as bucket,
                COUNT(CASE WHEN event_type = 'commit' THEN 1 END) as commits,
                COUNT(CASE WHEN event_type = 'pull_request' AND json_extract(data, '$.merged_at') IS NOT NULL THEN 1 END) as prs,
                COUNT(CASE WHEN event_type = 'issue' THEN 1 END) as issues
            FROM raw_events
            WHERE timestamp BETWEEN :start AND :end
            {bot_filter}
            GROUP BY bucket
            ORDER BY bucket
        """
        result = await self._session.execute(text(sql), {"start": ctx.start, "end": ctx.end})
        data = [
            {"bucket": row.bucket, "commits": row.commits, "prs": row.prs, "issues": row.issues}
            for row in result.mappings().all()
        ]
        return {"bucket_size": bucket_size, "data": data}

    async def velocity_ts(self, ctx: Timeframe) -> dict[str, Any]:
        bucket_expr, bucket_size = self._bucket_sql(ctx)
        sql = f"""
            SELECT
                {bucket_expr} as bucket,
                AVG(
                    (julianday(json_extract(data, '$.merged_at')) - julianday(json_extract(data, '$.created_at'))) * 24
                ) as avg_cycle_hours
            FROM raw_events
            WHERE source = 'github' AND event_type = 'pull_request'
            AND timestamp BETWEEN :start AND :end
            AND json_extract(data, '$.merged_at') IS NOT NULL
            GROUP BY bucket
            ORDER BY bucket
        """
        result = await self._session.execute(text(sql), {"start": ctx.start, "end": ctx.end})
        data = [
            {"bucket": row.bucket, "avg_cycle_hours": round(row.avg_cycle_hours, 2) if row.avg_cycle_hours else None}
            for row in result.mappings().all()
        ]
        return {"bucket_size": bucket_size, "data": data}

    async def collaboration_ts(self, ctx: Timeframe) -> dict[str, Any]:
        bucket_expr, bucket_size = self._bucket_sql(ctx)
        sql = f"""
            SELECT
                {bucket_expr} as bucket,
                COUNT(*) as reviews
            FROM raw_events
            WHERE source = 'github' AND event_type = 'pull_request_review'
            AND timestamp BETWEEN :start AND :end
            GROUP BY bucket
            ORDER BY bucket
        """
        result = await self._session.execute(text(sql), {"start": ctx.start, "end": ctx.end})
        data = [
            {"bucket": row.bucket, "reviews": row.reviews}
            for row in result.mappings().all()
        ]
        return {"bucket_size": bucket_size, "data": data}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _project_filter(self, ctx: Timeframe) -> str:
        """Not used directly in v1 SQL; projects are filtered in Python if needed."""
        return ""

    def _actor_filter(self, ctx: Timeframe) -> str:
        """Not used directly in v1 SQL; actors are filtered in Python if needed."""
        return ""
