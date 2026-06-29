## Context

This is a greenfield feature. There is no existing dashboard, metrics pipeline, or data ingestion from GitHub or Jira.

**v1 scope is deliberately small**: a single engineering manager runs the tool on their own machine to view their team's health. Multi-user, shared deployments, and auth are explicitly v2 — only revisited if v1 proves valuable. The architecture is chosen to make v1 easy to ship while not foreclosing v2 evolution.

The system must integrate with external APIs, store raw data per source for future drill-down, and present aggregated cross-system metrics in a single UI. The architecture must be extensible — Launchpad is planned as a third data source with its own entity model (merge proposals instead of PRs).

## Goals / Non-Goals

**Goals:**
- Ingest data from GitHub (commits, PRs, PR reviews, issues) and Jira (issues, sprints) on a schedule
- Store raw events per source in a normalized schema, preserving source-specific fields in a JSONB payload
- Compute aggregated metrics across systems (unified issue view, unified person view)
- Expose metrics via API, filterable by timeframe (date range or sprint), project, and person
- Provide a dashboard UI with Grafana-style timeframe selector and metric cards/charts
- Design the data-source provider interface to support future additions (Launchpad)
- Ship as a single-process local tool — `uv run project-health serve` and `uv run project-health backfill`

**Non-Goals (v1):**
- Real-time / webhook ingestion (batch/scheduled is sufficient)
- Alerting or notifications on metric thresholds
- Multi-user deployment, auth, SSO, admin UI for credentials
- Historical data migration (v1 starts fresh with forward-looking data + an explicit backfill)
- Custom metric definitions by end users
- Abandoned-PR rate (deferred to v2 once we have a sense of what's useful)
- Dedicated dependency-activity panel for bot PRs (bots are filtered in v1)
- Materialized views / pre-computed aggregations (on-the-fly + TTL cache for v1)

## Decisions

### 1. Deployment model — local single-user tool

The tool runs on the engineering manager's own machine as a long-running Python process. The HTTP server binds to `127.0.0.1` only. Configuration is a single YAML file (`./project-health.yaml` by default; `--config <path>` to override). No auth, no HTTPS, no session management.

**Implications:**
- The backend MUST be a long-running process. Serverless / CGI / per-request-spawn deployments are out.
- Operational story is two commands: `project-health serve` (web + scheduler) and `project-health backfill` (one-shot historical pull on first run).
- Multi-user evolution (v2) keeps the same data model and provider interfaces; only the deployment shell changes.

**Alternatives considered**: Containerized multi-process (web + worker + queue) — rejected for v1 as needless complexity for one user on one machine.

### 2. Tech stack

```
Backend:
  • Python 3.12+, managed by uv
  • FastAPI (async)
  • SQLAlchemy 2.x async + aiosqlite (raw SQL for hot aggregation queries; ORM for CRUD)
  • Alembic for migrations
  • Pydantic v2 for event/payload models and config validation
  • APScheduler for the in-process scheduler
  • Typer for the `project-health` CLI (serve, backfill, healthcheck)

Storage:
  • SQLite (JSON1 extension) — embedded, no separate database process
  • No Redis — in-memory TTL cache and per-provider in-memory mutex are sufficient
    for a single-process tool

Frontend:
  • React 18 + TypeScript + Vite
  • TanStack Query for fetching and client-side cache
  • Recharts for charts (declarative, lightweight; swap to ECharts only if a chart
    type genuinely warrants it)
  • Tailwind CSS for styling

API contract:
  • FastAPI auto-generates OpenAPI 3.x
  • Frontend types via openapi-typescript codegen — no hand-maintained duplication
```

### 3. Provider interface pattern

Each data source implements a `DataSourceProvider` Python `Protocol` with one method per event type it supports. Providers return empty lists for unsupported event types. A `DataSourceRegistry` holds active providers and APScheduler invokes them on a configurable interval (default 15 minutes).

```python
class DataSourceProvider(Protocol):
    id: str  # "github", "jira", "launchpad"

    async def fetch_commits(self, since: datetime) -> list[RawCommitEvent]: ...
    async def fetch_pull_requests(self, since: datetime) -> list[RawPREvent]: ...
    async def fetch_pull_request_reviews(self, since: datetime) -> list[RawReviewEvent]: ...
    async def fetch_issues(self, since: datetime) -> list[RawIssueEvent]: ...
    async def fetch_sprints(self) -> list[SprintDefinition]: ...
    async def health_check(self) -> bool: ...
```

**Alternatives considered**: Webhook-driven ingestion — rejected; adds infrastructure complexity for a dashboard that refreshes every few hours.

### 4. Raw event storage as source of truth

All ingested data is stored in a `raw_events` table before any aggregation. This ensures we can always recompute metrics, add new aggregations later, and drill down into per-source data.

```sql
CREATE TABLE raw_events (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,              -- "github", "jira"
  event_type TEXT NOT NULL,          -- "commit", "pull_request",
                                     -- "pull_request_review", "issue"
  external_id TEXT NOT NULL,         -- ID from source system
  timestamp DATETIME NOT NULL,       -- when the event occurred in the source (UTC)
  ingested_at DATETIME NOT NULL,     -- when we pulled it (UTC)
  actor TEXT,                        -- source-native identifier (username, accountId)
  project TEXT,                      -- repo key, project key
  data JSON NOT NULL                 -- source-specific payload (TEXT column, JSON1)
);

CREATE UNIQUE INDEX idx_raw_events_dedup
  ON raw_events(source, event_type, external_id);
CREATE INDEX idx_raw_events_source_ts ON raw_events(source, timestamp);
CREATE INDEX idx_raw_events_actor ON raw_events(actor);
CREATE INDEX idx_raw_events_project ON raw_events(project);
```

**Why JSON (SQLite JSON1)**: Each source has different fields (GitHub PRs have `additions`/`deletions`, Jira issues have `story_points`, Launchpad MPs have different shape). Storing source-specific data as a JSON text column avoids per-provider schema changes while keeping queries readable via `json_extract`. Migrating to PostgreSQL JSONB in v2 (if multi-user deployment warrants it) requires only dialect changes in the writer and aggregation queries — the schema shape stays the same.

Pull request reviews are stored as separate `raw_events` rows with `event_type = 'pull_request_review'`. Each review row captures the review state (`APPROVED | CHANGES_REQUESTED | COMMENTED`) and inline comment count in its `data` JSON column.

Records are never deleted: orphaned commits from force-pushes are harmless historical truth (see §13). PR LOC is captured at merge time and not maintained afterward.

### 5. Schedule-driven ingestion — in-process

APScheduler runs inside the FastAPI process. On boot, the scheduler registers one job per `(provider, event_type)` pair driven by the YAML's `ingestion.interval_minutes` (default 15).

**Concurrency control:** a per-provider in-memory `asyncio.Lock` prevents overlapping runs. If a tick fires while a previous run is still in flight, the new run is **skipped** (not queued) and logged. GitHub and Jira run on separate locks, so a slow Jira does not block GitHub.

**Incremental fetch:** `since` for each provider+event_type is read from `ingestion_runs` (§8) — specifically the `started_at` of the most recent successful run for that pair. This is cleaner than `MAX(timestamp) FROM raw_events` and resilient to out-of-order event delivery.

**Per-provider error isolation:** an exception in one provider does not halt others. Retries use exponential backoff (3 attempts) for transient API failures (5xx, network errors); permanent failures (401, 403) fail fast and surface in `ingestion_runs.error_message`.

### 6. First-run backfill via CLI

The first historical pull is operator-triggered, not automatic. The engineering manager runs:

```
project-health backfill --since 90d
```

This invokes the same provider code paths as the scheduler with `since = now - <window>` and writes through the same dedupe path. Running it again is safe: existing `external_id`s upsert. The default window is read from `ingestion.backfill_days` (default 90).

**Rationale**: backfill of a busy repo across 90 days can be thousands of API calls and several minutes of runtime. Doing this in a CLI keeps the dashboard responsive on first boot, gives the operator progress visibility in the terminal, and avoids burying a slow initial sync inside the scheduler loop.

### 7. Manual sync endpoint

`POST /api/sync/run` (optional `?source=github&event_type=pull_request`) triggers an immediate ingestion run for the specified scope, or all providers if unspecified. The endpoint contends on the same per-provider mutex as the scheduler:

- If the targeted provider is idle: a run starts; the endpoint returns `202 Accepted` with the new `ingestion_runs.id`.
- If the targeted provider is busy: the endpoint returns `409 Conflict` with the in-flight `ingestion_runs.id`. The UI button reads "Sync in progress" and is disabled until completion.

The endpoint is bound to localhost only (consistent with §1). No queuing of pending runs — click again after the current run finishes.

### 8. Ingestion observability — `ingestion_runs`

```sql
CREATE TABLE ingestion_runs (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  event_type TEXT NOT NULL,
  started_at DATETIME NOT NULL,
  finished_at DATETIME NULL,
  status TEXT NOT NULL,              -- running | success | failure | skipped
  trigger TEXT NOT NULL,             -- scheduled | manual | backfill
  events_count INTEGER NULL,
  error_message TEXT NULL
);

CREATE INDEX idx_ingestion_runs_source_event
  ON ingestion_runs(source, event_type, started_at);
```

The dashboard header displays a "Last synced" indicator per source, derived from the most recent `success` row per source. Stale-state escalation:

```
   green   < 1.5 × interval since last success
   amber   1.5 – 3 × interval
   red     > 3 × interval OR last run failed
```

### 9. Aggregation layer — on-the-fly with per-source TTL cache

For v1, metrics are computed on-the-fly from `raw_events` with a TTL-based in-memory cache.

- Aggregation API endpoints accept `timeframe` (`from`/`to` or `sprint_id`), `projects[]`, `actors[]`.
- Results are cached with a key derived from `(endpoint, query parameters, source set)`. Default TTL is 15 minutes — long enough to outlive a user staring at the dashboard, short enough that data is never wildly stale.
- **Cache invalidation is per-source, not global**: when a GitHub ingestion run completes, only cache entries whose source set includes GitHub are evicted. Jira ingestion does not invalidate pure-GitHub queries.
- Time-series (`/ts`) variants of key endpoints return bucketed data for sparklines and drill-down charts.
- Bucket size is auto-derived from the timeframe range: ≤7 days → daily, ≤90 days → weekly, ≤1 year → monthly, >1 year → quarterly.

**Alternatives considered**: Pre-computed materialized views — rejected for v1; on-the-fly is fast enough for one team's data volume with proper indexing.

### 10. Identity and team via YAML

People and projects are declared in the YAML config:

```yaml
team:
  - name: Jane Doe
    github: jdoe
    jira: 557058:abc-123-...     # accountId, optional
  - name: Bob Johnson
    github: bob-j                # GH only, no Jira identity

projects:
  github:
    - owner/repo-a
    - owner/repo-b
  jira:
    - key: PROJ
      board_id: 42               # required for sprint integration

bots:
  github:
    - dependabot[bot]
    - renovate[bot]
    - github-actions[bot]

credentials:
  github_token: ${GITHUB_TOKEN}
  jira:
    base_url: https://company.atlassian.net
    email: lbm@lilbignet.de
    api_token: ${JIRA_API_TOKEN}

ingestion:
  interval_minutes: 15
  backfill_days: 90

issue_type_mapping:              # optional, per source
  github:
    bug: bug
    enhancement: feature
    documentation: maintenance
  jira:
    Bug: bug
    Story: feature
    Task: maintenance
    Sub-task: maintenance
```

**Internal vs. external**: an actor present in the YAML `team` list (under any source identity) is "internal"; anyone else seen in `raw_events.actor` is "external." No separate flag needed.

**Env var refs** (`${GITHUB_TOKEN}`) are resolved at load time so credentials never sit in the YAML.

**Reconciliation into the database**: at boot, the YAML drives upserts into two tables:

```sql
CREATE TABLE persons (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1   -- SQLite boolean
);

CREATE TABLE person_identities (
  id TEXT PRIMARY KEY,
  person_id TEXT REFERENCES persons(id),  -- nullable: see auto-discovery
  source TEXT NOT NULL,
  external_id TEXT NOT NULL,
  UNIQUE (source, external_id)
);
```

Aggregations `LEFT JOIN person_identities` on `(raw_events.source, raw_events.actor) = (person_identities.source, person_identities.external_id)`. Unmapped identities still appear (no JOIN match) and are labeled by source (`GH: alice123`) in the UI, matching the existing "shown separately" requirement.

**Auto-discovery**: when ingestion encounters an `(source, external_id)` not in `person_identities`, it inserts a row with `person_id = NULL`. The CLI gains a `project-health identities list-unmapped` command that prints these for the operator to add to YAML.

### 11. Cycle time definition

**Cycle time = PR opened → PR merged.** This is the DORA-standard definition and is robust across local work styles (committing fluffy WIP vs. batching).

- Only `merged = true` PRs contribute.
- Drafts are not subtracted in v1 — `PR opened` is the `created_at` from GitHub even if the PR started as a draft. (A future refinement could use the `ready_for_review` timestamp; deferred.)
- Distributions are reported as median, p50, p90.

The earlier "first commit → merge" interpretation in the original spec was deliberately replaced.

### 12. LOC semantics

LOC is **PR-only** — `additions` and `deletions` from the merged PR. Commit-level additions/deletions are stored in `raw_events.data` but are **not** used for LOC aggregation, to avoid double-counting work that exists both as commits and as a merged PR.

- People table column renders as `+245 / −67` in a single cell.
- Inline background bar is sized by `additions + deletions`.
- Issue and PR counts have their own columns; LOC is bound to PRs.

The proposal frames LOC as a contextual signal, not a performance metric (Goodhart's law applies forcefully here).

### 13. PR size buckets — generated-file filter

Size buckets (`small <100`, `medium 100–500`, `large >500`) use `additions + deletions` **excluding files marked as `linguist-generated` or `linguist-vendored`** in `.gitattributes`. GitHub's diff API returns per-file changes; we exclude generated/vendored files and sum the rest.

Per-repo path-pattern overrides are a v2 affordance.

### 14. GitHub edge cases

| Case | Behavior |
|------|----------|
| Squash merges | Commit count per person is derived from PR-authored commits (the commits *in* the PR), not from `main`-branch traversal. The squash commit on `main` is ignored as a separate event. |
| Force-pushed branches | `raw_events` is append-only. Orphaned SHAs remain as historical truth — aggregations don't care if the SHA still resolves on GitHub. PR LOC is captured at merge time and not refreshed. |
| Co-authored-by | Credit only the primary author. Co-author trailers are stored in `data` for future use but do not contribute to per-person metrics in v1. |
| Closed-unmerged PRs | Stored in `raw_events` but excluded from all visible v1 metrics (LOC, cycle time, PR count). Abandoned-PR rate is a v2 candidate. |
| Bot PRs | Actors listed in YAML `bots.github` are filtered out of all human metrics. Stored in `raw_events` so a future "dependency activity" panel can surface them. |

### 15. Cross-system entity normalization

GitHub issues and Jira issues are treated as the same entity type for person-centric aggregation. Normalization happens at query time:

- **Issue type mapping**: GitHub labels → normalized type (`bug | feature | maintenance | other`). Jira issue type → normalized type. Driven by the optional `issue_type_mapping` YAML section; falls back to `other` for unmapped types.
- **PR / MR equivalence**: GitHub PRs and (future) Launchpad MPs both produce `pull_request` events with source-specific metadata in `data`.

### 16. Timeframe system

Timeframes are a unified abstraction passed to every query:

```
Timeframe =
  | { kind: "date_range"; start: datetime; end: datetime }
  | { kind: "sprint"; sprint_id: str; start: datetime; end: datetime }
```

Sprints are stored in a `sprints` table populated by the Jira provider. The UI offers:
- Grafana-style relative presets (Last 7d, 30d, 90d, This month, This quarter, This year)
- Absolute date-range picker (start → end)
- Sprint dropdown auto-populated from stored sprints (ordered by `end_date` DESC)

When a sprint is selected, downstream queries use the sprint's `start_date`/`end_date` as the time range.

**Active sprint with multiple Jira projects in the filter**: if more than one Jira project is selected and each has an active sprint, the sprint picker shows them grouped by project (`PROJ — Sprint 42 (active)`, `BACK — Sprint 17 (active)`). The default selection prefers an active sprint from the first project in the YAML projects list.

### 17. Dashboard component architecture

Tab-based navigation with a persistent shared header (timeframe selector + project filter + sync-freshness indicator). Tabs: "Projects" (default) and "People". Changing timeframe / project filter updates both pages.

```
AppShell
├── Header
│   ├── TabNav (Projects | People)
│   ├── TimeframeSelector
│   │   ├── RelativePresets (Last 7d, 30d, 90d, etc.)
│   │   ├── DateRangePicker (start/end)
│   │   └── SprintPicker (dropdown from /api/sprints)
│   ├── ProjectFilter (multi-select)
│   └── SyncStatusBadge ("Last synced 3m ago" + manual trigger)
│
├── ProjectsPage (default tab)
│   ├── SprintBurndown (only when sprint selected; stories only)
│   ├── MetricSection: Contribution Volume
│   ├── MetricSection: Velocity & Throughput
│   ├── MetricSection: Quality & Composition
│   └── MetricSection: Collaboration
│
└── PeoplePage
    ├── SummaryStats (contributor count, median PRs, median issues,
    │                 median cycle time)
    ├── PeopleTable (Name, Commits, PRs, LOC '+N/−M', Issues Resolved,
    │                Median Cycle Time, Reviews, Comments,
    │                Comments/Review)
    │   ├── SparklineColumn (sparkline on configured primary metric)
    │   ├── InlineBarViz (background bar proportional to column max)
    │   └── OutlierColorEncoding (toggleable, vs team median)
    └── PerPersonSections (visible when a row is selected)
        ├── MetricSection: Contribution Volume (scoped to person)
        ├── MetricSection: Velocity & Throughput (scoped to person)
        ├── MetricSection: Quality & Composition (scoped to person)
        └── MetricSection: Collaboration (reviews given + time-series)
```

Each metric component fetches from a dedicated aggregation endpoint via TanStack Query. `TimeframeSelector` and `ProjectFilter` emit changes that propagate through shared state. On the People page, the sprint picker functions as a date-range filter only (no burndown).

### 18. Future Launchpad integration

The provider interface already accommodates Launchpad: `fetch_pull_requests` returns `list[RawPREvent]` — Launchpad MPs map to this type with `source: "launchpad"`. The `data` JSON field carries MP-specific fields without schema changes. Person identity mapping extends to Launchpad usernames in YAML. No code changes needed in the aggregation or UI layers.

## Risks / Trade-offs

- **[Risk] GitHub/Jira API rate limits** → Mitigation: configurable ingestion interval, incremental `since` fetching, exponential backoff (3 attempts) on transient errors, fail-fast on auth errors.
- **[Risk] Query performance degrades as `raw_events` grows** → Mitigation: composite indexes on `(source, timestamp)`, `actor`, `project`; per-source cache reduces recompute pressure. SQLite handles single-user data volumes well; if data grows beyond ~10M rows, migration to PostgreSQL is the natural v2 step (schema shape is identical, only the dialect layer changes).
- **[Risk] Unmapped identities clutter the People view** → Mitigation: auto-discovery captures unmapped identities; `project-health identities list-unmapped` CLI gives the operator a one-step path to add them to YAML.
- **[Risk] Issue type normalization is inconsistent across projects** → Mitigation: configurable mapping per source; `other` bucket catches unmapped types; source-native labels visible on drill-down.
- **[Risk] Squash-merge + force-push can leave commit data that looks like garbage** → Accepted: aggregations don't rely on commit traversal; LOC is captured at PR-merge time.
- **[Trade-off] Single-process all-in-one** → Limits to one user, no horizontal scaling, restart pauses ingestion. Acceptable for v1; v2 deployment shell decouples web and worker.
- **[Trade-off] LOC as a displayed metric** → Goodhart's law applies. Framed as contextual signal in proposal; PR-only scope removes the easiest gaming surface (commit churn).

## v1 / v2 Scope

```
v1 — In scope
─────────────────────────────────────────
• Local single-user tool
• YAML-driven team, projects, credentials
• GitHub + Jira providers
• All decided metrics
• On-the-fly aggregation + per-source TTL cache
• Manual + scheduled ingestion + CLI backfill

v2 — Deferred until v1 proves valuable
─────────────────────────────────────────
• Multi-user / shared deployment
• Auth / SSO / admin UI
• Abandoned-PR rate
• Dedicated dependency-activity panel
• Materialized views for aggregation
• Real-time / webhook ingestion
• Launchpad provider
• Per-repo path-pattern overrides for size noise
• Co-author fractional credit
• Ready-for-review timestamp for cycle time
```

## Open Questions

- Charts: stick with Recharts, or accept ECharts up-front for the chord-diagram review matrix? (Recharts can do it but with more code.)
- Sparkline default primary metric: PRs merged, or issues resolved? (Settle on initial default; both are user-toggleable.)
