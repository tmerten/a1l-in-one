"""Aggregation core: timeframe resolution, classification, bucketing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel

from project_health.config.loader import Config, load_config


class Timeframe(BaseModel):
    """Normalized timeframe for queries."""

    kind: Literal["date_range", "sprint"]
    start: datetime
    end: datetime
    sprint_id: str | None = None


@dataclass
class AggregationContext:
    """Context passed to every aggregation query."""

    timeframe: Timeframe
    projects: list[str] | None = None
    actors: list[str] | None = None


def build_timeframe(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    sprint_id: str | None = None,
) -> Timeframe:
    """Build a normalized timeframe from query params."""
    if from_date and to_date:
        return Timeframe(kind="date_range", start=from_date, end=to_date)
    # Default to last 30 days
    now = datetime.now(timezone.utc)
    return Timeframe(
        kind="date_range",
        start=now - timedelta(days=30),
        end=now,
    )


def resolve_bucket_size(start: datetime, end: datetime) -> str:
    """Auto-derive bucket size from date range."""
    delta = end - start
    if delta <= timedelta(days=7):
        return "day"
    if delta <= timedelta(days=90):
        return "week"
    if delta <= timedelta(days=365):
        return "month"
    return "quarter"


def classify_pr_size(filtered_additions: int, filtered_deletions: int) -> str:
    """Classify PR size based on linguist-filtered LOC."""
    total = filtered_additions + filtered_deletions
    if total < 100:
        return "small"
    if total <= 500:
        return "medium"
    return "large"


def normalize_issue_type(source: str, raw_type: str, config: Config) -> str:
    """Normalize issue type using YAML mapping."""
    mapping = config.issue_type_mapping
    if source == "github":
        return mapping.github.get(raw_type, "other")
    if source == "jira":
        return mapping.jira.get(raw_type, "other")
    return "other"


BOT_CACHE: set[str] | None = None


def get_bot_set() -> set[str]:
    """Return cached bot set from config."""
    global BOT_CACHE
    if BOT_CACHE is None:
        try:
            cfg = load_config()
            BOT_CACHE = cfg.github_bots
        except Exception:
            BOT_CACHE = set()
    return BOT_CACHE
