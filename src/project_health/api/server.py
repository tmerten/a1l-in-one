"""FastAPI server with scheduler lifespan."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from project_health.config.loader import load_config
from project_health.db.reconcile import reconcile_persons_from_config
from project_health.db.session import get_session_maker
from project_health.ingestion.scheduler import SchedulerManager
from project_health.providers.registry import build_registry


def build_app(config_path: Path) -> FastAPI:
    """Build the FastAPI application with lifespan management."""

    config = load_config(config_path)
    scheduler = SchedulerManager(config)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        registry = await build_registry(config)
        app.state.registry = registry

        maker = get_session_maker()
        async with maker() as session:
            await reconcile_persons_from_config(session, config)
        scheduler.start()
        yield
        scheduler.shutdown()

    app = FastAPI(
        title="Project Health Dashboard",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.config = config

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from project_health.api.routes import metrics, persons, projects, sprints, sync

    app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
    app.include_router(sprints.router, prefix="/api/sprints", tags=["sprints"])
    app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
    app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])
    app.include_router(persons.router, prefix="/api/persons", tags=["persons"])

    return app


def create_app() -> FastAPI:
    """Factory for uvicorn --reload mode; reads config path from PROJECT_HEALTH_CONFIG env var."""
    import os

    config_path = Path(os.environ.get("PROJECT_HEALTH_CONFIG", "./project-health.yaml"))
    return build_app(config_path)


async def start_server(config_path: Path, host: str, port: int) -> None:
    """Start the uvicorn server."""
    import uvicorn

    app = build_app(config_path)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
