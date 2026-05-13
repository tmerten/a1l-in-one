# Project Health Dashboard

Local single-user project health dashboard with GitHub + Jira data ingestion. Runs entirely on your machine — no cloud required.

## Stack

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.x async, SQLite, APScheduler, Typer
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, TanStack Query, Recharts
- **Data sources:** GitHub (commits, PRs, reviews, issues), Jira (issues, sprints)

## Quick Start

```bash
# Install Python dependencies
uv sync

# Install frontend dependencies
cd frontend && npm install

# Configure
cp project-health.example.yaml project-health.yaml
# Edit project-health.yaml with your team, projects, and credentials
# Set required environment variables:
export GITHUB_TOKEN="ghp_..."
export JIRA_API_TOKEN="..."

# Run database migrations
uv run alembic upgrade head

# Backfill historical data (one-time)
uv run project-health backfill --since 90d

# Start the backend server (binds to 127.0.0.1:8000)
uv run project-health serve

# In another terminal, start the frontend dev server
# It proxies /api to the backend automatically
cd frontend && npm run dev
```

Then open http://localhost:5173

## Configuration

Copy `project-health.example.yaml` to `project-health.yaml` and fill in:

- `team` — team members with their GitHub / Jira identities
- `projects.github` — list of `owner/repo` strings
- `projects.jira` — project keys and board IDs
- `credentials` — API tokens (use `${ENV_VAR}` references)
- `ingestion` — scheduler interval and backfill window
- `issue_type_mapping` — optional normalization mapping

Credentials use `${ENV_VAR}` syntax and are resolved at load time.

## CLI Commands

```bash
# Start server with scheduler
uv run project-health serve

# Run a one-shot backfill
uv run project-health backfill --since 90d

# Check provider health
uv run project-health healthcheck

# List unmapped identities for operator review
uv run project-health identities list-unmapped
```

## Development

### Backend

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check src tests

# Type check
uv run mypy src

# Regenerate frontend types from OpenAPI schema
# (requires server to be running or schema exported)
uv run python -c "from project_health.api.server import build_app; import json; app = build_app('project-health.yaml'); print(json.dumps(app.openapi()))" > /tmp/openapi.json
cd frontend && npx openapi-typescript /tmp/openapi.json -o src/api/types.ts
```

### Frontend

```bash
cd frontend

# Dev server with HMR
npm run dev

# Production build
npm run build

# Type check
npx tsc --noEmit

# Regenerate types from backend
npm run typegen
```

## Architecture

- **SQLite** database (`project_health.db`) stores raw events, sprint definitions, person identities, and ingestion runs
- **Alembic** handles schema migrations
- **APScheduler** runs ingestion jobs in-process on a configurable interval
- **Per-provider locks** prevent overlapping runs
- **In-memory TTL cache** (15 min) for aggregation queries with per-source invalidation
- **FastAPI** auto-generates OpenAPI schema consumed by `openapi-typescript`

## v1 Scope

- Local single-user tool, localhost-only
- YAML-driven configuration
- GitHub + Jira providers
- Scheduled, manual, and CLI-driven ingestion
- All metrics: contribution volume, velocity, composition, collaboration, sprint burndown
- Per-source cache for aggregations

## v2 Ideas (Deferred)

- Multi-user deployment, auth, SSO
- Admin UI for credentials / identity mapping
- Abandoned-PR rate metric
- Materialized views for aggregation
- Real-time / webhook ingestion
- Launchpad provider
