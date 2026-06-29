"""Backfill CLI command implementation."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer

from project_health.config.loader import load_config
from project_health.db.session import get_session_maker
from project_health.ingestion.scheduler import IngestionRunner
from project_health.providers.registry import build_registry


def parse_since(value: str | None, default_days: int) -> datetime:
    """Parse a --since string like '90d' into a datetime."""
    if value is None:
        return datetime.now(UTC) - timedelta(days=default_days)
    value = value.strip().lower()
    if value.endswith("d"):
        days = int(value[:-1])
        return datetime.now(UTC) - timedelta(days=days)
    if value.endswith("h"):
        hours = int(value[:-1])
        return datetime.now(UTC) - timedelta(hours=hours)
    # Try ISO format
    return datetime.fromisoformat(value)


async def run_backfill(
    config_path: Path,
    source_filter: str | None,
    since_str: str | None,
) -> int:
    """Run backfill and return exit code (0 = success, 1 = at least one failure)."""
    config = load_config(config_path)
    registry = await build_registry(config)

    since = parse_since(since_str, config.ingestion.backfill_days)
    typer.echo(f"Backfill window: since {since.isoformat()}")

    providers = registry.all()
    if source_filter:
        provider = registry.get(source_filter)
        if provider is None:
            typer.echo(f"Unknown source: {source_filter}", err=True)
            return 1
        providers = [provider]

    any_failure = False
    event_types = [
        "commit",
        "pull_request",
        "change_request",
        "pull_request_review",
        "review_request",
        "review_decision",
        "review_comment",
        "issue",
        "sprint",
    ]

    maker = get_session_maker()
    for provider in providers:
        typer.echo(f"\n→ Backfilling {provider.id} ...")
        start_time = time.time()
        total_events = 0

        for et in event_types:
            async with maker() as session:
                runner = IngestionRunner(session)
                try:
                    result = await runner.run(
                        provider, et, trigger="backfill", force_since=since
                    )
                    if result.status == "success":
                        count = result.events_count or 0
                        total_events += count
                        typer.echo(f"  {et}: {count} events")
                    else:
                        any_failure = True
                        typer.echo(
                            f"  {et}: FAILED — {result.error_message}", err=True
                        )
                except Exception as exc:
                    any_failure = True
                    typer.echo(f"  {et}: FAILED — {exc}", err=True)

        elapsed = time.time() - start_time
        typer.echo(f"  Total: {total_events} events in {elapsed:.1f}s")

    return 1 if any_failure else 0
