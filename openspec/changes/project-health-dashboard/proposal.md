## Why

Engineering leads need a single dashboard to understand project health and team productivity across multiple systems (GitHub, Jira). Without it, assessing who contributes where, how fast work moves, and whether quality is improving requires manual data stitching across platforms. This change delivers that visibility, enabling data-backed conversations about output and performance — not to judge individuals, but to surface patterns, bottlenecks, and contributions across projects.

## What Changes

- New dashboard UI for project health overview with selectable timeframes (custom date ranges + Jira sprints)
- Data ingestion pipeline from GitHub (commits, PRs, issues) and Jira (issues, sprints)
- Aggregated metrics display across systems, with the ability to drill into raw per-system data
- Extensible data-source architecture supporting future additions (e.g., Launchpad)
- Person-centric view that treats issues from GitHub and Jira equivalently, showing resolved work across all platforms

### Metrics — v1

**Contribution volume:**
- Number of commits per project (selectable timeframe)
- Number of PRs per project with LOC added/removed
- Internal vs. external contribution ratio
- PRs per team member across all projects with LOC added/removed
- Issues opened vs. resolved per project and per person

**Velocity & throughput:**
- Cycle time (first commit to PR merge)
- PR review turnaround (PR opened to first review)

**Quality & composition:**
- Issue type breakdown (bug / feature / maintenance) across GitHub + Jira
- PR size distribution (small / medium / large)

**Collaboration:**
- PR review distribution (who reviews whose code)

**Time reference:**
- Custom date range selector (Grafana-style)
- Jira sprint selector as an alternative timeframe

## Capabilities

### New Capabilities

- `data-ingestion`: Pull and store raw metrics from GitHub and Jira on a schedule, with an extensible provider architecture for future data sources (Launchpad, etc.)
- `metrics-aggregation`: Compute aggregated metrics across data sources — per-project, per-person, and per-timeframe — treating equivalent entities (e.g., GitHub issues and Jira issues) uniformly
- `dashboard-ui`: Display project health metrics with Grafana-style timeframe selectors (custom date ranges + sprint dropdown), project/person toggles, and drill-down into per-system raw data
- `sprint-integration`: Integrate Jira sprints as a first-class timeframe reference, selectable alongside custom date ranges in all dashboard views

### Modified Capabilities

<!-- No existing capabilities to modify — this is a greenfield feature. -->

## Impact

- **New code**: Data ingestion service, aggregation layer, dashboard UI components, timeframe selector component
- **External dependencies**: GitHub API (commits, PRs, issues), Jira API (issues, sprints, boards)
- **Storage**: Raw metrics store (database or time-series store) and aggregation store
- **Infrastructure**: Scheduled ingestion jobs (cron or event-driven)
- **No breaking changes** — this is a new feature with no existing functionality impacted
