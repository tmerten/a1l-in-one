## Why

The dashboard currently treats Jira projects and GitHub repositories as peers — a flat list of interchangeable "projects." That does not match how the team actually works. Jira is the umbrella: all work items for the pulse (sprint, epic, task tracking) live there. GitHub is where the tasks get done — and a single developer may contribute to multiple GitHub repos during the same sprint. When an engineering manager looks at a developer over a timespan, they need to see **all** of that person's contributions in one place: their Jira issues (what was planned), their commits and PRs across every GitHub repo they touched (what was done), and — in the future — their Launchpad merge proposals, bugs, and comments.

Today the People page only surfaces GitHub reviewers and does not aggregate across sources. The project filter presents Jira project keys alongside GitHub repo slugs with no structural distinction. A developer who works across three GitHub repos and one Jira project has to be looked up four separate times. This change fixes that by making the person the primary axis and the datasource a secondary dimension — not the other way around.

## What Changes

- Introduce an explicit **datasource** abstraction that distinguishes planning/umbrella sources (Jira) from code/task sources (GitHub, future Launchpad). Datasources are not peers — they have different roles in the team's workflow.
- Redesign the **person-centric view** so that selecting a developer always shows their unified contributions across all configured sources — Jira issues, commits and PRs from every GitHub repo they participated in, and (later) Launchpad merge proposals.
- Replace the flat project filter with a **grouped project filter** that separates projects by datasource type, making it clear which are planning sources and which are code sources.
- Refactor the aggregation layer to support **cross-source person aggregation** natively — a single query path that resolves a person via `person_identities` and pulls their events from all sources.
- Ensure the provider interface and data model are ready for **Launchpad as a third datasource** without schema changes or aggregation-layer rework.

### Datasource roles

| Datasource | Role | Event types | Sprint? |
|---|---|---|---|
| Jira | Umbrella / planning | Issues, sprints | Yes (primary sprint source) |
| GitHub | Code / task execution | Commits, PRs, reviews, issues | No |
| Launchpad (future) | Code / task execution | Merge proposals, commits, bugs, comments | No |

### Person-centric view — what changes

When a developer is selected (or when viewing the People tab without a specific project filter), the dashboard shows:

- **Jira issues** assigned to or reported by that person (from the umbrella)
- **Commits** across all GitHub repos they contributed to
- **PRs** (authored + reviewed) across all GitHub repos
- **Issues** they opened or resolved on GitHub
- Future: Launchpad merge proposals, bugs, and comments

The key shift: the project filter is *additive* for person-centric views — it narrows which datasources/projects to include, but the default is "everything this person did across all sources."

### Project filter — what changes

The current flat `<select>` is replaced with a grouped selector:

```
Jira
  ├── PROJ
  └── ENG
GitHub
  ├── owner/repo-a
  ├── owner/repo-b
  └── owner/repo-c
```

Selecting a Jira project filters issues and sprints. Selecting a GitHub repo filters commits, PRs, reviews. Selecting none shows all. Multiple selections within a datasource are OR'd; across datasources, selections are independent.

## Capabilities

### New Capabilities

- `unified-person-view`: A person-centric contribution view that aggregates across all datasources (Jira + all GitHub repos) for a given person and timeframe, with per-source breakdowns available on drill-down.
- `datasource-abstraction`: An explicit datasource concept with role metadata (umbrella vs. code), grouped project listing, and a provider registration mechanism that makes adding Launchpad a config-and-implementation task — not an architecture change.

### Modified Capabilities

- `dashboard-ui`: ProjectFilter becomes grouped by datasource; PeoplePage uses unified-person-view data; AppShell datasource state propagation.
- `metrics-aggregation`: Aggregation queries gain cross-source person resolution; person-scoped queries default to all sources when no project filter is set.
- `data-ingestion`: Provider registry gains datasource role metadata; no provider code changes needed for existing GitHub and Jira providers.

## Impact

- **Database**: No schema changes. The existing `raw_events.source`, `person_identities`, and `persons` tables already support cross-source person resolution. A new `datasources` metadata layer is config-driven, not table-driven.
- **API**: New person-centric aggregation endpoints; modified projects endpoint returns grouped data; existing endpoints gain smarter defaults when no project filter is set.
- **Frontend**: ProjectFilter redesign; PeoplePage rewrite to consume unified-person-view data; minor AppShell changes for datasource-aware state.
- **Providers**: No breaking changes. Adding Launchpad later requires a new `LaunchpadProvider` class + YAML config entry + one line in `build_registry()`.

## v1 / v2 Scope

```
v1 — In scope
─────────────────────────────────────────
• Datasource abstraction with role metadata
• Grouped project filter in UI
• Unified person-centric view across Jira + GitHub
• Cross-source person aggregation in API
• Provider interface ready for Launchpad (no implementation)

v2 — Deferred
─────────────────────────────────────────
• Launchpad provider implementation
• Datasource-specific metric cards (e.g., "Jira burndown" vs "GitHub velocity")
• Per-datasource health indicators beyond sync freshness
• Cross-datasource issue linking (Jira ticket ↔ GitHub PR)
• Admin UI for datasource configuration
```
