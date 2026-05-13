"""FastAPI server with scheduler lifespan."""

from __future__ import annotations

import contextlib
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from project_health.config.loader import load_config
from project_health.db.reconcile import reconcile_persons_from_config
from project_health.db.session import get_session_maker
from project_health.ingestion.scheduler import SchedulerManager


def build_app(config_path: Path) -> FastAPI:
    """Build the FastAPI application with lifespan management."""
    config = load_config(config_path)
    scheduler = SchedulerManager(config)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: reconcile identities and start scheduler
        maker = get_session_maker()
        async with maker() as session:
            await reconcile_persons_from_config(session, config)
        scheduler.start()
        yield
        # Shutdown
        scheduler.shutdown()

    app = FastAPI(
        title="Project Health Dashboard",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.config = config

    # CORS for local dev (frontend on different port)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from project_health.api.routes import metrics, sprints, sync

    app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
    app.include_router(sprints.router, prefix="/api/sprints", tags=["sprints"])
    app.include_router(metrics.router, prefix="/api/metrics", tags=["metrics"])

    return app


async def start_server(config_path: Path, host: str, port: int) -> None:
    """Start the uvicorn server."""
    import uvicorn

    app = build_app(config_path)
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()
