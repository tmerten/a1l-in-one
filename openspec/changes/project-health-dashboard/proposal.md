## Why

An engineering manager needs a single view of project health and team productivity across multiple systems (GitHub, Jira). Without it, assessing who contributes where, how fast work moves, and whether quality is improving requires manual data stitching across platforms. This change delivers that visibility, enabling data-backed conversations about output and performance — not to judge individuals, but to surface patterns, bottlenecks, and contributions across projects.

**v1 is a local single-user tool.** It runs on the engineering manager's own machine. Multi-user / shared deployment is intentionally deferred until v1 proves valuable.

**Framing note on LOC and similar metrics.** Lines of code, PR counts, and review counts are *contextual signals*, not performance scores. Goodhart's law applies — once a measure becomes a target, it ceases to be a good measure. The dashboard surfaces these to spark conversation, not to rank people.

## What Changes

- New dashboard UI for project health overview with selectable timeframes (custom date ranges + Jira sprints)
- Data ingestion pipeline from GitHub (commits, PRs, PR reviews, issues) and Jira (issues, sprints)
- Aggregated metrics display across systems, with the ability to drill into raw per-system data
- Extensible data-source architecture supporting future additions (Launchpad)
- Person-centric view that treats issues from GitHub and Jira equivalently, showing resolved work across platforms
- Single YAML config file declaring team members, projects, credentials, and optional issue-type mapping
- CLI tool with `serve` and `backfill` commands; manual "Sync now" trigger in the UI

### Metrics — v1

**Contribution volume:**
- Number of commits per project (selectable timeframe; squash-merged PRs counted via their PR's commits, not via `main`)
- Number of PRs per project with LOC added/removed (displayed as `+N / −M`)
- Internal vs. external contribution ratio (internal = present in YAML `team` list)
- PRs per team member across all projects with LOC added/removed
- Issues opened vs. resolved per project and per person (unified across GitHub + Jira)

**Velocity & throughput:**
- Cycle time (PR opened → PR merged; DORA-standard definition)
- PR review turnaround (PR opened to first review)

**Quality & composition:**
- Issue type breakdown (bug / feature / maintenance / other) across GitHub + Jira
- PR size distribution (small <100 LOC / medium 100–500 / large >500), excluding files marked `linguist-generated` or `linguist-vendored`

**Collaboration:**
- PR review distribution (who reviews whose code)
- Per-person review activity (reviews, comments, comments-per-review, by review state)

**Time reference:**
- Custom date range selector (Grafana-style)
- Jira sprint selector as an alternative timeframe

### Filters and exclusions

- **Bot PRs**: actors listed in the YAML `bots.github` section (Dependabot, Renovate, github-actions by default) are stored in `raw_events` but filtered from all human metrics.
- **Closed-unmerged PRs**: stored but excluded from LOC, cycle time, and PR count. Abandoned-PR rate is a v2 candidate.
- **Co-authored-by**: only the primary author is credited in v1.

## Capabilities

### New Capabilities

- `data-ingestion`: Pull and store raw metrics from GitHub and Jira on a schedule, driven by YAML config, with an in-process scheduler, CLI backfill, manual sync endpoint, and observability via an `ingestion_runs` table. Extensible provider architecture for future sources (Launchpad).
- `metrics-aggregation`: Compute aggregated metrics across data sources — per-project, per-person, and per-timeframe — treating equivalent entities (e.g., GitHub issues and Jira issues) uniformly. On-the-fly queries with per-source TTL cache.
- `dashboard-ui`: Display project health metrics with Grafana-style timeframe selectors (custom date ranges + sprint dropdown), project/person toggles, drill-down into per-system raw data, and a sync-freshness indicator with manual-trigger button.
- `sprint-integration`: Integrate Jira sprints as a first-class timeframe reference, selectable alongside custom date ranges in all dashboard views.

### Modified Capabilities

<!-- No existing capabilities to modify — this is a greenfield feature. -->

## Impact

- **New code**: Python backend (FastAPI + SQLAlchemy 2.x async + APScheduler + Pydantic v2 + Typer), React frontend (Vite + TanStack Query + Recharts + Tailwind).
- **External dependencies**: GitHub API (commits, PRs, PR reviews, issues), Jira API (issues, sprints, boards).
- **Storage**: PostgreSQL 15+ with JSONB. Tables: `raw_events`, `sprints`, `persons`, `person_identities`, `ingestion_runs`. No Redis.
- **Infrastructure**: None beyond a Postgres instance. The tool runs as a single long-running Python process bound to localhost; ingestion is scheduled in-process by APScheduler.
- **No breaking changes** — this is a new feature with no existing functionality impacted.

## v1 / v2 Scope

```
v1 — In scope
─────────────────────────────────────────
• Local single-user tool, localhost-only
• YAML config for team, projects, credentials
• GitHub + Jira providers
• Scheduled + manual + CLI-driven ingestion
• All metrics listed above
• Per-source TTL cache for aggregations

v2 — Deferred
─────────────────────────────────────────
• Multi-user / shared deployment, auth, SSO
• Admin UI for credentials / identity mapping
• Abandoned-PR rate metric
• Dedicated dependency-activity panel
• Materialized aggregation views
• Webhook / real-time ingestion
• Launchpad provider
• Per-repo path overrides for PR-size noise
• Co-author fractional credit
• Ready-for-review timestamp in cycle time
```
