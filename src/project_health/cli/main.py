"""CLI entry point for project-health."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from project_health.cli.backfill import run_backfill

app = typer.Typer(
    name="project-health",
    help="Project Health Dashboard — GitHub + Jira ingestion & metrics",
    no_args_is_help=True,
)


@app.command()
def serve(
    config: Path = typer.Option(
        Path("./project-health.yaml"),
        "--config",
        "-c",
        help="Path to YAML configuration file",
        exists=True,
        readable=True,
    ),
    host: str = typer.Option("127.0.0.1", "--host", help="Bind address (127.0.0.1 enforced in v1)"),
    port: int = typer.Option(8000, "--port", "-p", help="HTTP port"),
) -> None:
    """Start the dashboard server with in-process scheduler."""
    from project_health.api.server import start_server

    asyncio.run(start_server(config, host, port))


@app.command()
def backfill(
    config: Path = typer.Option(
        Path("./project-health.yaml"),
        "--config",
        "-c",
        help="Path to YAML configuration file",
        exists=True,
        readable=True,
    ),
    source: str | None = typer.Option(None, "--source", help="Limit backfill to a specific source"),
    since: str | None = typer.Option(None, "--since", help="Backfill window (e.g. 90d)"),
) -> None:
    """Run a one-shot historical ingestion backfill."""
    code = asyncio.run(run_backfill(config, source, since))
    raise typer.Exit(code)


@app.command()
def healthcheck(
    config: Path = typer.Option(
        Path("./project-health.yaml"),
        "--config",
        "-c",
        help="Path to YAML configuration file",
        exists=True,
        readable=True,
    ),
) -> None:
    """Verify all configured data sources are reachable."""
    from project_health.config.loader import load_config
    from project_health.providers.registry import build_registry

    async def _check() -> int:
        cfg = load_config(config)
        registry = await build_registry(cfg)
        ok = True
        for provider in registry.all():
            healthy = await provider.health_check()
            if healthy:
                typer.echo(f"✓ {provider.id} — OK")
            else:
                typer.echo(f"✗ {provider.id} — UNREACHABLE", err=True)
                ok = False
        return 0 if ok else 1

    code = asyncio.run(_check())
    raise typer.Exit(code)


@app.command(name="list-unmapped")
def identities_list_unmapped(
    config: Path = typer.Option(
        Path("./project-health.yaml"),
        "--config",
        "-c",
        help="Path to YAML configuration file",
        exists=True,
        readable=True,
    ),
) -> None:
    """Print unmapped person identities for operator review."""
    import asyncio

    from sqlalchemy import select

    from project_health.db.models import PersonIdentity
    from project_health.db.session import get_session_maker

    async def _list() -> None:
        maker = get_session_maker()
        async with maker() as session:
            result = await session.execute(
                select(PersonIdentity).where(PersonIdentity.person_id.is_(None))
            )
            rows = result.scalars().all()
            if not rows:
                typer.echo("No unmapped identities.")
                return
            by_source: dict[str, list[str]] = {}
            for row in rows:
                by_source.setdefault(row.source, []).append(row.external_id)
            for source, ids in sorted(by_source.items()):
                typer.echo(f"{source}:")
                for ext_id in sorted(ids):
                    typer.echo(f"  - {ext_id}")

    asyncio.run(_list())


if __name__ == "__main__":
    app()
