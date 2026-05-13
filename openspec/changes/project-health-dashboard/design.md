## Context

This is a greenfield feature. There is no existing dashboard, metrics pipeline, or data ingestion from GitHub or Jira. The system must integrate with external APIs, store raw data per source for future drill-down, and present aggregated cross-system metrics in a single UI. The architecture must be extensible — Launchpad is planned as a third data source with its own entity model (merge proposals instead of PRs).

## Goals / Non-Goals

**Goals:**
- Ingest data from GitHub (commits, PRs, issues) and Jira (issues, sprints) on a schedule
- Store raw events per source in a normalized schema, preserving source-specific fields in a flexible payload
- Compute aggregated metrics across systems (unified issue view, unified person view)
- Expose metrics via API, filterable by timeframe (date range or sprint), project, and person
- Provide a dashboard UI with Grafana-style timeframe selector and metric cards/charts
- Design the data-source provider interface to support future additions (Launchpad)

**Non-Goals:**
- Real-time streaming ingestion (batch/scheduled is sufficient for v1)
- Alerting or notifications on metric thresholds
- Historical data migration (v1 starts fresh with forward-looking data)
- Authentication/authorization (assumes single-tenant or existing auth layer)
- Custom metric definitions by end users

## Decisions

### 1. Provider Interface Pattern

Each data source implements a `DataSourceProvider` interface with methods for each event type it supports. Providers return `null` or empty for unsupported event types. A `DataSourceRegistry` holds active providers and a scheduler invokes them.

```typescript
interface DataSourceProvider {
  id: string;                    // "github", "jira", "launchpad"
  fetchCommits(since: Date): Promise<RawCommitEvent[]>;
  fetchPullRequests(since: Date): Promise<RawPREvent[]>;
  fetchPullRequestReviews(since: Date): Promise<RawReviewEvent[]>;
  fetchIssues(since: Date): Promise<RawIssueEvent[]>;
  fetchSprints(): Promise<SprintDefinition[]>;
  healthCheck(): Promise<boolean>;
}
```

**Alternatives considered**: Webhook-driven ingestion (rejected — adds infrastructure complexity; batch polling is simpler and adequate for a dashboard that refreshes every few hours).

### 2. Raw Event Storage as Source of Truth

All ingested data is stored in a `raw_events` table before any aggregation. This ensures we can always recompute metrics, add new aggregations later, and drill down into per-source data. The schema:

```sql
CREATE TABLE raw_events (
  id UUID PRIMARY KEY,
  source VARCHAR NOT NULL,           -- "github", "jira"
  event_type VARCHAR NOT NULL,       -- "commit", "pull_request", "issue", "sprint"
  external_id VARCHAR NOT NULL,      -- ID from source system
  timestamp TIMESTAMPTZ NOT NULL,    -- when the event occurred in the source
  ingested_at TIMESTAMPTZ NOT NULL,  -- when we pulled it
  actor VARCHAR,                     -- person identifier (username, accountId)
  project VARCHAR,                   -- repo key, project key
  data JSONB NOT NULL                -- source-specific payload
);

CREATE INDEX idx_raw_events_source_ts ON raw_events(source, timestamp);
CREATE INDEX idx_raw_events_actor ON raw_events(actor);
CREATE INDEX idx_raw_events_project ON raw_events(project);
```

**Why JSONB for `data`**: Each source has different fields (GitHub PRs have `additions`/`deletions`, Jira issues have `story_points`, Launchpad MPs have different fields). JSONB lets us store source-specific data without schema changes per provider, while still allowing indexed queries via GIN.

Pull request reviews are stored as separate `raw_events` rows with `event_type = 'pull_request_review'`. Each review event captures the review state (`APPROVED | CHANGES_REQUESTED | COMMENTED`) and inline comment count in its `data` JSONB column. This enables per-person review activity queries without extracting nested data from PR payloads.

### 3. Aggregation Layer — On-the-Fly Queries with Caching

For v1, metrics are computed on-the-fly from `raw_events` with a TTL-based cache. This avoids the complexity of materialized views and refresh logic while keeping the dashboard responsive for common queries.

- Aggregation API endpoints accept `timeframe` (start/end or sprint_id), `projects[]`, `actors[]`
- Results cached with a key derived from query parameters, TTL of 5 minutes
- Cache invalidated after each ingestion run
- Time-series (`/ts`) variants of key endpoints return bucketed data for sparklines and drill-down charts
- Bucket size is auto-derived from the timeframe range: ≤7 days → daily, ≤90 days → weekly, ≤1 year → monthly, >1 year → quarterly

**Alternatives considered**: Pre-computed materialized views (rejected for v1 — adds refresh complexity; on-the-fly is fast enough for moderate data volumes with proper indexing).

### 4. Cross-System Entity Normalization

GitHub issues and Jira issues are treated as the same entity type for person-centric aggregation. Normalization happens at query time:

- **Issue type mapping**: GitHub labels → normalized type (bug/feature/maintenance). Jira issue type → normalized type. Configurable mapping per project.
- **Person identity mapping**: Configurable mapping file linking GitHub usernames to Jira account IDs (and future Launchpad usernames). Without mapping, each system identity is shown separately but labeled by source.
- **PR/MR equivalence**: GitHub PRs and Launchpad Merge Proposals both produce `pull_request` events with source-specific metadata in `data`.

### 5. Timeframe System

Timeframes are a unified abstraction passed to every query:

```
type Timeframe =
  | { kind: "date_range"; start: Date; end: Date }
  | { kind: "sprint"; sprintId: string; start: Date; end: Date }
```

Sprints are stored in a `sprints` table populated by the Jira provider. The UI offers:
- Grafana-style relative presets (Last 7 days, Last 30 days, Last 90 days, This month, This quarter)
- Absolute date range picker (start → end)
- Sprint dropdown (auto-populated from stored sprints, ordered by end date descending)

When a sprint is selected, the underlying query uses the sprint's start/end dates as the time range.

### 6. Dashboard Component Architecture

The dashboard uses a tab-based navigation with a persistent shared header (timeframe selector + project filter). The two tabs are "Projects" (default) and "People". Changing the timeframe or project filter updates both pages.

```
AppShell
├── Header
│   ├── TabNav (Projects | People)
│   ├── TimeframeSelector
│   │   ├── RelativePresets (Last 7d, 30d, 90d, etc.)
│   │   ├── DateRangePicker (start/end)
│   │   └── SprintPicker (dropdown from /api/sprints)
│   └── ProjectFilter (multi-select)
│
├── ProjectsPage (default tab)
│   ├── SprintBurndown (only when sprint selected, stories only)
│   ├── MetricSection: Contribution Volume
│   │   ├── CommitCountChart
│   │   ├── PRCountChart (with LOC delta)
│   │   ├── InternalVsExternalRatio
│   │   ├── PRsPerProjectTable
│   │   └── IssuesOpenedVsResolvedChart
│   ├── MetricSection: Velocity & Throughput
│   │   ├── CycleTimeChart
│   │   └── PRReviewTurnaroundChart
│   ├── MetricSection: Quality & Composition
│   │   ├── IssueTypeBreakdown
│   │   └── PRSizeDistribution
│   └── MetricSection: Collaboration
│       └── ReviewDistributionMatrix
│
└── PeoplePage
    ├── SummaryStats (contributor count, median PRs, median issues, median cycle time)
    ├── PeopleTable (columns: name, commits, PRs, LOC, issues resolved, median cycle time, reviews, comments, comments/review)
    │   ├── SparklineColumn (sparkline on primary metric)
    │   ├── InlineBarViz (background bar proportional to column max)
    │   └── OutlierColorEncoding (toggleable, relative to team median)
    └── PerPersonSections (visible when a person row is clicked)
        ├── MetricSection: Contribution Volume (scoped to selected person)
        ├── MetricSection: Velocity & Throughput (scoped to selected person)
        ├── MetricSection: Quality & Composition (scoped to selected person)
        └── MetricSection: Collaboration (reviews given by this person with reviewee breakdown + time-series)
```

Each metric component fetches from a dedicated aggregation endpoint. The `TimeframeSelector` and `ProjectFilter` emit changes that propagate to all components via shared state. On the People page, sprint picker is available but only acts as a date-range filter (no sprint-specific charts like burndown).

### 7. Future Launchpad Integration

The provider interface already accommodates Launchpad: `fetchPullRequests` returns `RawPREvent[]` — Launchpad MPs map to this type with `source: "launchpad"`. The `data` JSONB field carries MP-specific fields (e.g., diff size, branch info) without schema changes. Person identity mapping extends to Launchpad usernames. No code changes needed in the aggregation or UI layers.

## Risks / Trade-offs

- **[Risk] GitHub/Jira API rate limits** → Mitigation: Configurable ingestion interval (default every 15 min), incremental fetching with `since` parameter, exponential backoff on rate-limit errors.
- **[Risk] Query performance degrades as `raw_events` grows** → Mitigation: Composite indexes on (source, timestamp, actor, project); partition by month in future; cache layer in front of aggregation queries.
- **[Risk] Person identity mapping is incomplete or stale** → Mitigation: Show per-source breakdown alongside aggregated view; make mapping file easy to update; unmapped identities still appear labeled by source.
- **[Risk] Issue type normalization is inconsistent across projects** → Mitigation: Configurable mapping per project; show source-native type as secondary label.
- **[Trade-off] Batch polling vs real-time** → Batch is simpler to build and operate; dashboard users don't need sub-minute freshness. Acceptable for v1.

## Open Questions

- What is the hosting environment? (determines cron vs task-queue scheduling, database choice beyond PostgreSQL)
- Is there an existing identity/SSO system we can leverage for person mapping?
- How many projects and users are expected initially? (informs caching and partition strategy)
- Do we need an admin UI for configuring provider credentials and issue-type mappings, or is config-file sufficient for v1?
- What is the preferred frontend framework? (React, Vue, etc.)
