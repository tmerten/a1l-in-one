## 1. Project Scaffolding

- [ ] 1.1 Initialize Python project with `uv init`, target Python 3.12+
- [ ] 1.2 Add backend dependencies: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic`, `pydantic-settings`, `apscheduler`, `typer`, `httpx`, `pyyaml`
- [ ] 1.3 Add dev dependencies: `pytest`, `pytest-asyncio`, `pytest-postgresql`, `ruff`, `mypy`
- [ ] 1.4 Create module layout: `src/project_health/{config,ingestion,providers,aggregation,api,cli,db}`
- [ ] 1.5 Scaffold React frontend with Vite + TypeScript template under `frontend/`
- [ ] 1.6 Add frontend dependencies: `@tanstack/react-query`, `recharts`, `tailwindcss`, `openapi-typescript`, `react-router-dom`
- [ ] 1.7 Configure Tailwind, Vite proxy to FastAPI at `/api`
- [ ] 1.8 Add `project-health` console script entry point (Typer app)

## 2. Configuration & YAML Loader

- [ ] 2.1 Define Pydantic models for the YAML config (`TeamMember`, `GithubProject`, `JiraProject`, `Credentials`, `IngestionSettings`, `IssueTypeMapping`, `BotsConfig`, `Config`)
- [ ] 2.2 Implement YAML loader with `${ENV_VAR}` reference resolution at load time
- [ ] 2.3 Validate config on load: required fields, project keys, credentials present
- [ ] 2.4 Surface clear error messages for missing env vars or malformed YAML
- [ ] 2.5 Provide a sample `project-health.example.yaml` in repo root
- [ ] 2.6 Support `--config <path>` CLI flag; default to `./project-health.yaml`

## 3. Database Schema & Migrations

- [ ] 3.1 Configure Alembic with async SQLAlchemy
- [ ] 3.2 Migration: create `raw_events` table with columns from design §4, unique index on `(source, event_type, external_id)`, secondary indexes on `(source, timestamp)`, `actor`, `project`
- [ ] 3.3 Migration: create `sprints` table (id, name, project, start_date, end_date, state)
- [ ] 3.4 Migration: create `persons` table (id, display_name, active)
- [ ] 3.5 Migration: create `person_identities` table (id, person_id nullable, source, external_id, unique on (source, external_id))
- [ ] 3.6 Migration: create `ingestion_runs` table (id, source, event_type, started_at, finished_at, status, trigger, events_count, error_message)
- [ ] 3.7 Implement boot-time reconciliation: upsert `persons` and `person_identities` from YAML `team` list

## 4. Provider Interface

- [ ] 4.1 Define `DataSourceProvider` Protocol with `fetch_commits`, `fetch_pull_requests`, `fetch_pull_request_reviews`, `fetch_issues`, `fetch_sprints`, `health_check`
- [ ] 4.2 Define Pydantic event models: `RawCommitEvent`, `RawPREvent`, `RawReviewEvent`, `RawIssueEvent`, `SprintDefinition`
- [ ] 4.3 Implement `DataSourceRegistry` that instantiates providers from validated config
- [ ] 4.4 Implement `EventWriter` that upserts events into `raw_events` keyed on `(source, event_type, external_id)`

## 5. GitHub Provider

- [ ] 5.1 Implement GitHub API client (`httpx.AsyncClient`) with token auth, pagination helper, conditional-request support (`If-Modified-Since`)
- [ ] 5.2 Implement `fetch_commits(since)` — iterate repos, paginate commits, return `RawCommitEvent[]`
- [ ] 5.3 Implement `fetch_pull_requests(since)` — paginate PRs, include `additions`, `deletions`, `state`, `merged_at`, `reviewers`, `linguist_filtered_additions`, `linguist_filtered_deletions` in `data` payload (compute filtered values per-file)
- [ ] 5.4 Implement `fetch_pull_request_reviews(since)` — paginate reviews per recent PR, include `review_state` and `comment_count` in `data` payload
- [ ] 5.5 Implement `fetch_issues(since)` — paginate issues, exclude PRs, include labels and state in `data` payload
- [ ] 5.6 Implement `health_check()` — verify token validity and repository access
- [ ] 5.7 Implement `fetch_sprints()` returning empty (GitHub has no sprints)
- [ ] 5.8 Handle GitHub rate limits: respect `X-RateLimit-Remaining` and `Retry-After`; exponential backoff on 5xx; fail fast on 401/403

## 6. Jira Provider

- [ ] 6.1 Implement Jira API client (`httpx.AsyncClient`) with basic auth (email + API token)
- [ ] 6.2 Implement `fetch_issues(since)` — JQL `updated >= since`, paginate, include `issue_type`, `story_points`, `status`, `labels` in `data` payload
- [ ] 6.3 Implement `fetch_sprints()` — query board sprints endpoint, return `SprintDefinition[]`
- [ ] 6.4 Implement `health_check()` — verify credentials and project/board access
- [ ] 6.5 Implement `fetch_commits`, `fetch_pull_requests`, `fetch_pull_request_reviews` returning empty (Jira has none)

## 7. Scheduler (in-process)

- [ ] 7.1 Configure APScheduler with `AsyncIOScheduler`, attach to FastAPI lifespan
- [ ] 7.2 Register one job per `(provider, event_type)` pair on `ingestion.interval_minutes`
- [ ] 7.3 Implement per-provider `asyncio.Lock` registry; ticks acquire-or-skip
- [ ] 7.4 Implement `IngestionRunner`: creates `ingestion_runs` row, derives `since` from last successful run, calls provider, writes events, updates row with `status` and `events_count`
- [ ] 7.5 Per-provider error isolation — exceptions in one job do not affect others
- [ ] 7.6 Retry transient failures (5xx, network) with exponential backoff (3 attempts); fail fast on auth errors
- [ ] 7.7 Structured logging for run start, success (count), failure (with error), skip (lock contention)

## 8. Backfill CLI Command

- [ ] 8.1 `project-health backfill [--source <id>] [--since 90d]` command in Typer app
- [ ] 8.2 Reuses `IngestionRunner` with `trigger='backfill'` and `since = now - window`
- [ ] 8.3 Default window from `ingestion.backfill_days`; CLI flag overrides
- [ ] 8.4 Print per-provider progress (events fetched, time elapsed)
- [ ] 8.5 Exit code reflects overall success/failure

## 9. Manual Sync Endpoint

- [ ] 9.1 `POST /api/sync/run` with optional query params `source`, `event_type`
- [ ] 9.2 Returns `202 Accepted` with new `ingestion_runs.id` when provider idle
- [ ] 9.3 Returns `409 Conflict` with in-flight `ingestion_runs.id` when provider busy
- [ ] 9.4 `GET /api/sync/status` returns per-source freshness (last success + status)
- [ ] 9.5 Bind FastAPI to `127.0.0.1` only (config validates this in v1)

## 10. Identity Tooling

- [ ] 10.1 Boot-time auto-discovery: on `EventWriter` insert, capture any new `(source, actor)` not in `person_identities` as a row with `person_id = NULL`
- [ ] 10.2 `project-health identities list-unmapped` CLI command prints unmapped identities for operator review
- [ ] 10.3 Internal-vs-external classifier: actor present in YAML `team` (under any source) → internal; everyone else → external

## 11. Sprint Storage & API

- [ ] 11.1 Upsert sprints from `Jira.fetch_sprints()` into `sprints` table
- [ ] 11.2 `GET /api/sprints?project=<key>` returns sprints ordered by `end_date` DESC, last 90 days completed + all active
- [ ] 11.3 Active-sprint detection; include `"is_active": true` flag in response

## 12. Aggregation Core

- [ ] 12.1 Timeframe resolver — normalize `{date_range}` and `{sprint_id}` into `(start, end)`
- [ ] 12.2 Issue type normalizer — apply YAML `issue_type_mapping` per source; fall back to `other`
- [ ] 12.3 Person identity resolver — `LEFT JOIN person_identities` to collapse cross-source identities
- [ ] 12.4 PR size classifier — bucket by `linguist_filtered_additions + linguist_filtered_deletions` from `data`: small <100, medium 100–500, large >500
- [ ] 12.5 Internal/external classifier — derived from YAML `team` membership of the resolved person
- [ ] 12.6 Bot filter — exclude actors in YAML `bots.github` from human metric queries
- [ ] 12.7 Time-series bucket generator — auto-derive bucket from range: ≤7d daily, ≤90d weekly, ≤1y monthly, >1y quarterly

## 13. Aggregation Metrics

- [ ] 13.1 Commit count per project / per person — exclude squash-merge commits on `main` (count via PR-associated commits)
- [ ] 13.2 PR count with `additions` / `deletions` per project and per person — merged PRs only
- [ ] 13.3 Issues opened vs resolved per project and per person — unified GitHub + Jira
- [ ] 13.4 Internal vs external contribution ratio
- [ ] 13.5 Cycle time — `PR.created_at` to `PR.merged_at` for merged PRs; produce median, p50, p90
- [ ] 13.6 PR review turnaround — `PR.created_at` to first non-author review; produce median, p50, p90
- [ ] 13.7 Issue type breakdown (bug / feature / maintenance / other) with unified counts
- [ ] 13.8 PR size distribution using §12.4
- [ ] 13.9 Review distribution matrix — reviewer × author counts
- [ ] 13.10 Per-person review activity — reviews count, inline comment count, comments/review, review state breakdown
- [ ] 13.11 Per-person reviewee breakdown — who this person reviewed, counts per reviewee

## 14. Aggregation API Endpoints

- [ ] 14.1 `GET /api/metrics/contribution-volume` — commits, PRs (+N/−M), issues opened/resolved, internal/external ratio
- [ ] 14.2 `GET /api/metrics/velocity` — cycle time and PR review turnaround distributions
- [ ] 14.3 `GET /api/metrics/composition` — issue type breakdown and PR size distribution
- [ ] 14.4 `GET /api/metrics/collaboration` — review matrix; per-person review activity when `actors[]` set
- [ ] 14.5 `GET /api/metrics/sprint-burndown` — committed-vs-completed story points (with issue-count fallback)
- [ ] 14.6 Common query params across endpoints: `from`, `to`, `sprint_id`, `projects[]`, `actors[]`
- [ ] 14.7 Per-source breakdown in responses (total + per-source detail for drill-down)
- [ ] 14.8 Bot filter applied to all human-metric endpoints; bots stored but never surfaced in v1

## 15. Aggregation API — Time-Series

- [ ] 15.1 `GET /api/metrics/contribution-volume/ts` — bucketed commit count, PR count + LOC, issues opened/resolved per bucket
- [ ] 15.2 `GET /api/metrics/velocity/ts` — bucketed cycle time and review turnaround
- [ ] 15.3 `GET /api/metrics/collaboration/ts` — bucketed per-person review activity when `actors[]` set
- [ ] 15.4 All `/ts` endpoints share bucket sizing from §12.7

## 16. Aggregation Caching

- [ ] 16.1 In-memory cache keyed on `(endpoint, query params, source set)` with 15-minute TTL
- [ ] 16.2 Per-source invalidation: completed GitHub ingestion run evicts entries whose source set includes GitHub
- [ ] 16.3 Cache hit/miss counters surfaced via `/api/sync/status` for visibility

## 17. Dashboard — Shell & Shared Header

- [ ] 17.1 React app shell with tab navigation (Projects | People), shared header
- [ ] 17.2 Generate frontend types via `openapi-typescript` from FastAPI OpenAPI schema; wire into TanStack Query hooks
- [ ] 17.3 Shared timeframe state in URL search params; persists across tab switches
- [ ] 17.4 Relative-preset selector (Last 7d, 30d, 90d, This month, This quarter, This year)
- [ ] 17.5 Absolute date-range picker (start → end calendar)
- [ ] 17.6 Sprint picker dropdown from `GET /api/sprints`; group by project when multiple projects active; "(active)" badge
- [ ] 17.7 Default timeframe: active sprint from first YAML Jira project if any, else "Last 30 days"
- [ ] 17.8 Project multi-select filter from YAML projects
- [ ] 17.9 `SyncStatusBadge` — last-synced indicator per source with green/amber/red escalation; "Sync now" button calls `POST /api/sync/run`

## 18. Dashboard — Projects Page

- [ ] 18.1 Page layout with `SprintBurndown` (sprint-mode only) + four metric sections
- [ ] 18.2 `SprintBurndown` — committed vs completed story points with carried-over count; fallback to issue count with note
- [ ] 18.3 Contribution Volume: commit count chart, PR count chart with stacked `+N`/`−M` bars, internal-vs-external donut, per-project table, issues opened vs resolved grouped-bar chart
- [ ] 18.4 Velocity & Throughput: cycle time distribution (histogram with p50/p90 markers), PR review turnaround distribution
- [ ] 18.5 Quality & Composition: issue type breakdown (stacked bar or donut), PR size distribution (bar chart with counts and percentages); hover shows per-source breakdown
- [ ] 18.6 Collaboration: review distribution matrix (heatmap or table)

## 19. Dashboard — People Page

- [ ] 19.1 Page layout: summary stats row + people table + per-person drill-down sections
- [ ] 19.2 Summary stats: contributor count, median PRs, median issues resolved, median cycle time
- [ ] 19.3 People table — sortable columns: Name, Commits, PRs, LOC (`+N / −M`), Issues Resolved, Median Cycle Time, Reviews, Comments, Comments/Review
- [ ] 19.4 Inline background bars on numeric cells, scaled to column max
- [ ] 19.5 Sparkline column driven by `/ts` endpoint for configured primary metric
- [ ] 19.6 Outlier color encoding (green above median, red below) — toggleable
- [ ] 19.7 Unmapped identities render as separate rows labeled by source (`GH: alice123`)
- [ ] 19.8 Row selection → all sections below scope to that person; "Clear" returns to team view
- [ ] 19.9 Per-person Contribution Volume, Velocity & Throughput, Quality & Composition sections
- [ ] 19.10 Per-person Collaboration: reviews given with reviewee breakdown, time-series trend, review state breakdown

## 20. Dashboard — Drill-down & Raw Data

- [ ] 20.1 Drill-down on issue counts: click expands per-source breakdown (GitHub vs Jira)
- [ ] 20.2 Drill-down on issue type segments: source-native labels alongside normalized type
- [ ] 20.3 Raw event list view: filtered table of `raw_events` for current drill-down

## 21. Dashboard — Loading, Error, Empty States

- [ ] 21.1 Skeleton / spinner state per metric component
- [ ] 21.2 Per-component error state with retry button (errors in one component do not break others)
- [ ] 21.3 "No data for this period" empty state per component and for People table

## 22. Dashboard — Settings Panel

- [ ] 22.1 Show/hide toggle per metric section (shared across Projects and People)
- [ ] 22.2 Outlier color encoding toggle
- [ ] 22.3 Sparkline primary metric selector
- [ ] 22.4 Persist preferences in `localStorage` (display-only; no team/identity edits in v1)

## 23. Integration & Polish

- [ ] 23.1 End-to-end test: scheduler tick → events stored → API returns metrics → dashboard renders
- [ ] 23.2 CLI smoke test: `project-health backfill --since 7d` against a test fixture
- [ ] 23.3 People page drill-down test: select person → scoped re-render → clear → team view
- [ ] 23.4 Bot filter test: bot-authored PR exists in `raw_events` but absent from all human-metric responses
- [ ] 23.5 Squash-merge test: PR-associated commits counted; squash commit on `main` not double-counted
- [ ] 23.6 Cycle time test: PR with `created_at` and `merged_at` produces correct median/p50/p90
- [ ] 23.7 Per-source cache invalidation test: GitHub ingestion does not invalidate Jira-only query results
- [ ] 23.8 Document YAML config format and provider interface for future Launchpad integration
- [ ] 23.9 Run `ruff check`, `mypy`, `pytest` and `tsc --noEmit` / `vite build`; fix issues
