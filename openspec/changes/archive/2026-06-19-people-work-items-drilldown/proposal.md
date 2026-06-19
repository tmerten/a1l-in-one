## Why

The People view currently shows only aggregated numbers per person: commits, PRs merged, issues resolved, reviews, cycle time. While useful for a high-level pulse, an engineering manager cannot see *what* those numbers represent. "47 commits" tells you nothing about which features were built, which bugs were fixed, or what work is currently in progress. The manager has to leave the dashboard and manually cross-reference Jira and GitHub to understand the concrete work behind the metrics.

This change adds drill-down capability to show individual work items behind each metric — pull requests, issues, commits, and reviews — with their titles, descriptions, status, and links. It also surfaces currently active work items (open PRs, in-progress Jira issues) so the manager can see what the team is working on *right now*.

## What Changes

- Add a **Work Items API endpoint** that returns individual raw_events for a person, filtered by event type, status, and time range.
- Extend the **Person Detail page** with a "Work Items" section showing:
  - **Completed work items** during the selected time range (merged PRs, resolved issues, commits)
  - **Active work items** (open PRs, in-progress Jira issues, draft PRs)
- Each work item card displays: title, project/repo, status badge, timestamp, and external link.
- Allow filtering by datasource (GitHub/Jira) and event type (PRs, issues, commits, reviews).
- Add a "View all work items" action from the People table that pre-filters to that person.

### What "Work Items" Means

| Datasource | Event Type | Work Item |
|------------|------------|-----------|
| GitHub | `pull_request` | Pull Request (open/merged/closed) |
| GitHub | `issue` | GitHub Issue |
| GitHub | `commit` | Commit (linked to PR when available) |
| GitHub | `pull_request_review` | PR Review |
| Jira | `issue` | Jira Issue (Bug, Feature, Task, etc.) |

### Active vs Completed

- **Active**: Open PRs, draft PRs, Jira issues with status not in "Done" or "Closed"
- **Completed**: Merged PRs, closed issues, commits within the time range

## Capabilities

### New Capabilities

- `work-items-api`: API endpoint returning paginated work items for a person, with filtering by datasource, event type, status, and time range.
- `work-items-drilldown`: UI component in PersonDetailPage showing completed and active work items with titles, descriptions, links, and filtering.

### Modified Capabilities

- `person-detail-page`: Extended with Work Items section alongside existing summary cards and charts.
- `people-table`: Row action to view work items for that person (navigates to PersonDetailPage with work items expanded).

## Impact

- **Database**: No schema changes. Queries use existing `raw_events` table with person identity resolution.
- **API**: New endpoint `GET /api/persons/{person_id}/work-items` with pagination and filtering.
- **Frontend**: New `WorkItemsSection` component; extended `PersonDetailPage`; new hooks for fetching work items.
- **Performance**: Pagination (20 items/page) prevents over-fetching; active items query is bounded to current state (no time range).

## v1 / v2 Scope

```
v1 — In scope
─────────────────────────────────────────
• Work Items API with pagination
• Work items list in PersonDetailPage
• Completed work items (time-filtered)
• Active work items (current state)
• Filter by datasource and event type
• Links to external URLs

v2 — Deferred
─────────────────────────────────────────
• Full-text search across work item titles/descriptions
• Bulk export (CSV/JSON)
• Work item grouping by epic/sprint
• Work item timeline visualization
• Cross-datasource linking (Jira ticket ↔ GitHub PR)
```
