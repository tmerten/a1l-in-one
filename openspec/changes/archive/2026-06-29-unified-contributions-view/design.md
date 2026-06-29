## Context

The existing dashboard already has a working provider interface (`DataSourceProvider` Protocol), a `raw_events` table with a `source` column, `person_identities` for cross-source identity resolution, and a `persons` table. The GitHub and Jira providers are functional. The aggregation layer computes metrics per-source but does not have a unified person-scoped query path that defaults to "all sources."

The gap is not a missing table or a missing provider — it is a missing **conceptual layer**. The codebase lacks:

1. A datasource abstraction that carries role metadata (umbrella vs. code) and groups projects by source type.
2. A person-centric aggregation path that resolves a person once and pulls their events from all sources.
3. A UI that treats the person as the primary axis and the datasource as a secondary grouping dimension.

This design adds that conceptual layer on top of the existing infrastructure, without schema migrations.

## Goals / Non-Goals

**Goals:**
- Introduce a `Datasource` concept with `id`, `role` (umbrella | code), `display_name`, and associated projects
- Redesign the person-centric view so selecting a developer shows all their contributions across all configured sources
- Replace the flat project filter with a grouped selector organized by datasource
- Make the aggregation layer support cross-source person queries natively
- Ensure adding Launchpad requires only a new provider class + config entry + one registry line — no architecture changes

**Non-Goals (v1):**
- Launchpad provider implementation (architecture readiness only)
- Cross-datasource issue linking (Jira ticket ↔ GitHub PR auto-association)
- Changing the Projects page — it continues to show per-project metrics, just with a better filter
- Multi-select within the project filter for v1 (single-select per datasource group; "all" is the default)

## Decisions

### 1. Datasource metadata is config-driven, not a database table

Datasources are defined in the YAML config and materialized at boot time. They are not persisted in a separate database table because:

- The set of datasources is small and stable (2–3 in v1).
- Datasource metadata (role, display name) is configuration, not runtime state.
- Adding a database table for 2–3 rows with no foreign keys is over-engineering.

The `DataSourceRegistry` gains a `datasources` property that returns `list[Datasource]` — a new Pydantic model:

```python
class DatasourceRole(str, Enum):
    UMBRELLA = "umbrella"
    CODE = "code"

class Datasource(BaseModel):
    id: str                          # "github", "jira", "launchpad"
    role: DatasourceRole
    display_name: str                # "GitHub", "Jira", "Launchpad"
    projects: list[str]              # ["owner/repo-a", "owner/repo-b"]
    is_configured: bool              # True if credentials present + at least one project
```

`build_registry()` already conditionally instantiates providers. It now also populates `datasources` from the config. Unconfigured sources (e.g., Launchpad with no credentials) appear with `is_configured=False` — the UI can show them as "available but not connected."

**Alternatives considered**: A `datasources` database table — rejected for the reasons above. A static Python enum — rejected because it doesn't carry per-deployment project lists.

### 2. Person-centric view is the default for the People tab

Currently, the People page requires selecting a project first and then shows reviewers for that project. This is inverted relative to how the team works.

**New behavior:**

- The People page loads with **no project filter** and shows every resolved person from the `persons` table.
- Each person row displays aggregated metrics across **all** sources and **all** projects.
- The project filter, when used, *narrows* the view — it doesn't enable it.
- Selecting a person row drills into their per-source breakdown (Jira issues, GitHub PRs across repos, etc.).

**Rationale**: An engineering manager's primary question is "What did Jane do this sprint?" — not "What did Jane do in repo-a?" The answer should include Jane's Jira issues, commits in repo-a, PRs in repo-b, and reviews in repo-c.

### 3. Unified person aggregation query path

A new `person_contributions()` method on `AggregationQueries` replaces the current approach of filtering by `actor` (which is source-specific and doesn't resolve identities). The new path:

1. Resolve the person to all their identities: `SELECT external_id, source FROM person_identities WHERE person_id = ?`
2. Query `raw_events` using `(source, actor) IN (identity_pairs)` — a single query across all sources.
3. Group results by `source` and `project` for drill-down.

This is a single SQL query, not N queries per source:

```sql
SELECT source, event_type, project, COUNT(*), ...
FROM raw_events
WHERE (source, actor) IN (
    SELECT source, external_id FROM person_identities WHERE person_id = ?
)
AND timestamp BETWEEN ? AND ?
GROUP BY source, event_type, project
```

For unmapped identities (`person_id IS NULL`), the query falls back to the old `actor = ?` path with `source = ?` — so auto-discovered identities still appear.

### 4. Grouped project filter design

The current `ProjectFilter` is a single `<select>` with a flat list. It is replaced with a `DatasourceProjectFilter` component:

```
┌──────────────────────────────────────┐
│ All sources                  [v]     │
├──────────────────────────────────────┤
│ ▸ Jira                               │
│    ○ All Jira projects               │
│    ○ PROJ                            │
│    ○ ENG                             │
│ ▸ GitHub                             │
│    ○ All GitHub projects             │
│    ○ owner/repo-a                    │
│    ○ owner/repo-b                    │
│    ○ owner/repo-c                    │
└──────────────────────────────────────┘
```

- The top-level "All sources" option clears all filters (default).
- Expanding a datasource group shows its projects.
- Selecting a project within a group filters to that datasource + project.
- "All Jira projects" / "All GitHub projects" filters to that datasource only.
- Only one project can be selected per datasource group in v1. Multi-select within a group is v2.

**State encoding in URL**: `?datasource=github&project=owner/repo-a` replaces the current `?projects=owner/repo-a`. The `projects` param is deprecated but still accepted for backward compatibility.

### 5. Modified projects endpoint

`GET /api/projects` currently returns `string[]`. It changes to return grouped data:

```json
{
  "datasources": [
    {
      "id": "jira",
      "role": "umbrella",
      "display_name": "Jira",
      "projects": ["PROJ", "ENG"]
    },
    {
      "id": "github",
      "role": "code",
      "display_name": "GitHub",
      "projects": ["owner/repo-a", "owner/repo-b"]
    }
  ]
}
```

The old flat format is available via `GET /api/projects?format=flat` for backward compatibility during migration.

### 6. New person-centric API endpoints

**`GET /api/persons`** — List all resolved persons with summary metrics across all sources:

```json
{
  "persons": [
    {
      "id": "p-1",
      "display_name": "Jane Doe",
      "identities": [
        {"source": "github", "external_id": "jdoe"},
        {"source": "jira", "external_id": "557058:abc-123"}
      ],
      "metrics": {
        "commits": 47,
        "prs_opened": 12,
        "prs_merged": 10,
        "pr_loc_added": 2340,
        "pr_loc_removed": 567,
        "issues_resolved": 8,
        "issues_opened": 3,
        "reviews_given": 15,
        "review_comments": 42,
        "median_cycle_time_hours": 18.5,
        "sources": {
          "github": { "commits": 47, "prs_merged": 10, "..." },
          "jira": { "issues_resolved": 8, "issues_opened": 3 }
        }
      }
    }
  ]
}
```

Query params: `from`, `to`, `sprint_id`, `datasource`, `project` (narrowing filters).

**`GET /api/persons/{person_id}/contributions`** — Detailed per-person, per-source, per-project breakdown:

```json
{
  "person_id": "p-1",
  "display_name": "Jane Doe",
  "timeframe": { "kind": "sprint", "start": "...", "end": "..." },
  "contributions": [
    {
      "datasource": "jira",
      "role": "umbrella",
      "projects": [
        {
          "project": "PROJ",
          "issues_resolved": 5,
          "issues_opened": 2,
          "issues_by_type": { "bug": 1, "feature": 3, "maintenance": 1 }
        }
      ]
    },
    {
      "datasource": "github",
      "role": "code",
      "projects": [
        {
          "project": "owner/repo-a",
          "commits": 30,
          "prs_merged": 6,
          "pr_loc_added": 1500,
          "pr_loc_removed": 300,
          "reviews_given": 8
        },
        {
          "project": "owner/repo-b",
          "commits": 17,
          "prs_merged": 4,
          "pr_loc_added": 840,
          "pr_loc_removed": 267,
          "reviews_given": 7
        }
      ]
    }
  ]
}
```

This endpoint replaces the current approach of calling multiple metric endpoints with `?actors=<login>`.

### 7. PeoplePage redesign

The PeoplePage is rewritten around the new endpoints:

```
PeoplePage
├── SummaryRow (total contributors, total PRs, total issues resolved, median cycle time)
├── PeopleTable
│   ├── Columns: Name, Commits, PRs, LOC (+N/−M), Issues Resolved,
│   │            Reviews, Cycle Time
│   ├── Data from GET /api/persons
│   ├── Per-source mini-badges on hover (GH: 47 commits, Jira: 8 issues)
│   ├── Sortable, inline background bars
│   └── Row click → selects person
│
└── PersonDetail (visible when row selected)
    ├── PersonHeader (name, identity badges per source)
    ├── PerDatasourceSections
    │   ├── JiraSection (umbrella role badge)
    │   │   ├── Issues resolved/opened by type
    │   │   └── Per-project breakdown if multiple Jira projects
    │   └── GitHubSection (code role badge)
    │       ├── Commits, PRs, LOC per repo
    │       ├── Reviews given across repos
    │       └── Per-repo breakdown
    └── CrossSourceSummary (totals across all sources)
```

The key UX change: when a person is selected, their contributions are **organized by datasource**, not by metric type. The Jira section shows planning work; the GitHub section shows code work. This reflects the team's mental model.

### 8. AppShell datasource-aware state

The AppShell header gains:

- **DatasourceProjectFilter** replacing `ProjectFilter` (see §4)
- **Datasource health indicators** in `SyncStatusBadge` — each configured datasource shows its sync freshness independently

The shared filter state in URL search params changes:
- `?datasource=jira&project=PROJ` replaces `?projects=PROJ`
- The old `?projects=` param is accepted but mapped to the new format internally
- `?from=...&to=...` and `?sprint_id=...` remain unchanged

### 9. Launchpad readiness — no schema changes

Adding Launchpad as a third datasource requires:

1. A new `LaunchpadProvider` class implementing `DataSourceProvider`
2. A `launchpad` section in `projects` and `credentials` in YAML config
3. One line in `build_registry()` to instantiate it
4. `Datasource(id="launchpad", role=DatasourceRole.CODE, ...)` appears automatically

**No changes to:**
- `raw_events` schema (Launchpad merge proposals map to `RawPREvent` with `source="launchpad"`; bugs map to `RawIssueEvent`; comments map to `RawReviewEvent`)
- `person_identities` schema (Launchpad usernames are just another source)
- Aggregation queries (they already use `source` as a grouping dimension)
- The person-centric view (it iterates over all configured sources)

The only frontend change would be a "Launchpad" section appearing in the grouped project filter and in per-person detail — driven by the datasources API response, not by hardcoded source names.

### 10. Aggregation query refactoring

Current aggregation queries in `queries.py` often hard-code `source = 'github'` for GitHub-only metrics (cycle time, collaboration). These are refactored to:

- Use a `_source_filter()` helper that builds the appropriate `WHERE source IN (...)` clause based on which datasources are configured and which support the given event type.
- A `source_capabilities` dict on each `Datasource` object lists which event types it provides:

```python
SOURCE_CAPABILITIES: dict[str, set[str]] = {
    "github": {"commit", "pull_request", "pull_request_review", "issue"},
    "jira": {"issue", "sprint"},
    "launchpad": {"pull_request", "pull_request_review", "commit", "issue"},  # future
}
```

This replaces hard-coded `source = 'github'` checks and makes the queries datasource-agnostic. If Launchpad later provides `pull_request` events, cycle time queries automatically include them. If Launchpad provides `issue` events (bugs), they appear alongside Jira and GitHub issues in the unified issue view. If Launchpad provides `pull_request_review` events (comments on merge proposals), they join the collaboration metrics.

## Risks / Trade-offs

- **[Risk] Person resolution latency for large teams** → Mitigation: the `person_identities` table is small (N persons × M sources). The `IN (identity_pairs)` subquery is fast with the existing `(source, external_id)` unique index.
- **[Risk] Over-fetching when "all sources" default produces too much data** → Mitigation: time-bounded queries (sprint or date range) naturally limit the result set. The per-source TTL cache covers the common case.
- **[Risk] UI complexity from grouped filter** → Mitigation: the grouped filter collapses by default; most users will use "All sources" or expand only one group. It is simpler than the current flat list once the user understands the grouping.
- **[Trade-off] Single-select per datasource group in v1** → Limits filtering to one Jira project + one GitHub repo at a time. Acceptable for v1; multi-select within a group is a UI-only change in v2.
- **[Trade-off] No cross-datasource issue linking** → A Jira ticket and its linked GitHub PR are not automatically associated in v1. The user sees them as separate rows under different datasource sections. Linking requires a dedicated mapping layer — deferred to v2.

## Open Questions

- Should the People page default to "current sprint" or "last 30 days" when no timeframe is set? (Current default is "last 30 days"; the team may prefer the active sprint.)
- Should the grouped project filter use an accordion (collapsible sections) or a dropdown with section headers? (Accordion is proposed; dropdown is more compact.)
