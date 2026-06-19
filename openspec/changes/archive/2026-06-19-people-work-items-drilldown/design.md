## Context

The dashboard already stores all raw events in the `raw_events` table, including full payloads for pull requests, issues, commits, and reviews. The `person_identities` table maps persons to their external identities across datasources. The aggregation layer (`AggregationQueries`) can resolve a person to their identities and query events across sources.

The gap is that there is no API endpoint or UI component to display individual events — only aggregated counts. This design adds a query path and UI surface for rendering work items without schema changes.

## Goals / Non-Goals

**Goals:**
- Expose a paginated API endpoint for a person's work items
- Show work items in PersonDetailPage with titles, status, links
- Distinguish active work items (in progress) from completed work items
- Allow filtering by datasource and event type

**Non-Goals (v1):**
- Full-text search across work item content
- Cross-datasource linking (Jira ↔ GitHub)
- Editing or updating work item status from the dashboard

## Decisions

### 1. Work Items API Endpoint

**`GET /api/persons/{person_id}/work-items`**

Query parameters:
- `status`: `active` | `completed` (default: `completed`)
- `datasource`: `github` | `jira` | `launchpad` (optional)
- `event_type`: `pull_request` | `issue` | `commit` | `pull_request_review` (optional)
- `from`, `to`: time range for completed items (required when `status=completed`)
- `page`, `per_page`: pagination (default: 1, 20)

Response:
```json
{
  "person_id": "p-1",
  "status": "completed",
  "total": 47,
  "page": 1,
  "per_page": 20,
  "items": [
    {
      "id": "evt-123",
      "datasource": "github",
      "event_type": "pull_request",
      "external_id": "42",
      "project": "owner/repo",
      "title": "Fix null pointer in auth handler",
      "description": "Adds null check before dereferencing user object...",
      "status": "merged",
      "timestamp": "2026-06-15T10:32:00Z",
      "url": "https://github.com/owner/repo/pull/42",
      "metadata": {
        "additions": 45,
        "deletions": 12,
        "reviewers": ["alice", "bob"]
      }
    },
    {
      "id": "evt-456",
      "datasource": "jira",
      "event_type": "issue",
      "external_id": "PROJ-123",
      "project": "PROJ",
      "title": "Implement user authentication",
      "description": "As a user, I want to log in...",
      "status": "Done",
      "timestamp": "2026-06-10T14:00:00Z",
      "url": "https://jira.example.com/browse/PROJ-123",
      "metadata": {
        "issue_type": "Feature",
        "story_points": 5,
        "labels": ["auth", "security"]
      }
    }
  ]
}
```

**Implementation:**
- Query `raw_events` filtered by `(source, actor) IN (person_identities)`
- For `status=active`: filter by event-specific active states (open PRs, non-Done Jira issues)
- For `status=completed`: filter by time range and completion states (merged PRs, closed issues)
- Order by `timestamp DESC` for completed, by `timestamp DESC` for active (most recently touched first)

### 2. Active Work Items Definition

| Event Type | Active Status |
|------------|---------------|
| GitHub PR | `state=open` (including drafts) |
| GitHub Issue | `state=open` |
| Jira Issue | Status not in `Done`, `Closed`, `Cancelled` |
| Commit | N/A (commits are always completed) |
| PR Review | N/A (reviews are always completed) |

Active items query ignores `from`/`to` parameters — it returns current state.

### 3. Pagination Strategy

- Default 20 items per page
- Cursor-based pagination considered, but offset-based (`page=N`) is simpler and sufficient for v1
- Total count returned for UI pagination controls
- No infinite scroll in v1 — explicit pagination

### 4. Work Item Card Component

Each work item renders as a card:

```
┌──────────────────────────────────────────────────────────────┐
│ [GH] Fix null pointer in auth handler            [merged]   │
│ owner/repo • PR #42 • 2026-06-15                   [↗ Open] │
│ Adds null check before dereferencing user object...          │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ [Jira] Implement user authentication                  [Done] │
│ PROJ • PROJ-123 • 2026-06-10                       [↗ Open]  │
│ As a user, I want to log in... • Feature • 5 pts             │
└──────────────────────────────────────────────────────────────┘
```

Elements:
- Datasource badge (GH/Jira/LP)
- Title (truncated if long)
- Status badge (color-coded: green for merged/done, blue for open/in-progress, yellow for draft)
- Project/repo and external ID
- Timestamp (relative: "3 days ago")
- External link button
- Description snippet (truncated to 2 lines)
- Metadata chips (LOC for PRs, story points for Jira, issue type)

### 5. Work Items Section in PersonDetailPage

Location: Below existing summary cards and charts, collapsible section.

```
PersonDetailPage
├── PersonHeader (name, identity badges)
├── SummaryCards (Commits, PRs, Issues, Reviews, Cycle Time)
├── ChartsSection (collapsible)
│   ├── ContributionVolumeChart
│   ├── VelocityChart
│   └── CollaborationChart
└── WorkItemsSection (new, collapsible)
    ├── SectionHeader
    │   ├── Sprint/date range label
    │   └── ViewToggle [Grouped] [Timeline]
    ├── ShippedSection (when status=completed)
    │   ├── FilterBar
    │   │   ├── DatasourceFilter [All | GitHub | Jira]
    │   │   └── EventTypeFilter [All | PRs | Issues | Commits | Reviews]
    │   └── WorkItemsList (grouped or timeline view)
    └── ActiveWorkSection (always visible, separate)
        └── WorkItemCard[]
```

**Default behavior**: Grouped view, expanded when navigated from People table.

### 6. View Toggle: Grouped vs Timeline

Two presentation modes for shipped work items, controlled by toggle in section header.

**Toggle mechanics:**
- Position: Inline with section header, next to sprint/date label
- Default: Grouped view
- State persisted in URL: `?view=grouped` or `?view=timeline`
- Smooth transition between views (no page reload)

**Grouped view:**

Work items organized by datasource, then by event type:

```
┌─ Jira Issues (3) ──────────────────────────────────────────────────────┐
│  PROJ-123  Implement user authentication           ✓ Done • 5 pts    │
│  PROJ-130  Fix login timeout for mobile users      ✓ Done • 2 pts    │
│  PROJ-145  Add password reset flow                ✓ Done • 3 pts    │
└────────────────────────────────────────────────────────────────────────┘

┌─ Pull Requests (4) ───────────────────────────────────────────────────┐
│  #42  Fix null pointer in auth handler    ✓ merged  2d ago    [↗]   │
│       owner/repo • +45 −12 • 2 reviewers                              │
│                                                                        │
│  #47  Add rate limiting middleware        ✓ merged  4d ago    [↗]   │
│       owner/repo • +234 −56 • 3 reviewers                             │
│                                                                        │
│  #52  Refactor auth middleware chain      ✓ merged  6d ago    [↗]   │
│       owner/repo • +180 −45 • 1 reviewer                              │
│                                                                        │
│  #38  Mobile login responsive fix         ✓ merged  5d ago    [↗]   │
│       owner/repo2 • +89 −23 • 2 reviewers                             │
└────────────────────────────────────────────────────────────────────────┘

┌─ Commits (47) ─────────────────────────────────────────────────────────┐
│  47 commits across 4 PRs                                          [▸] │
└────────────────────────────────────────────────────────────────────────┘
```

Each datasource section is collapsible. User can expand/collapse Jira, PRs, or Commits independently.

**Timeline view:**

Work items in chronological order, grouped by day:

```
Jun 15
  ├── 10:32  [GH] #42 merged: Fix null pointer in auth handler
  │         owner/repo • +45 −12 • 2 reviewers               [↗]
  │
  └── 09:15  [Jira] PROJ-123 → Done: Implement user authentication
            Feature • 5 pts • auth, security                   [↗]

Jun 14
  ├── 16:00  [GH] #47 merged: Add rate limiting middleware
  │         owner/repo • +234 −56 • 3 reviewers              [↗]
  │
  └── 14:20  [Jira] PROJ-130 → Done: Fix login timeout for mobile
            Bug • 2 pts • mobile                                [↗]

Jun 13
  └── 11:00  [GH] #52 merged: Refactor auth middleware chain
            owner/repo • +180 −45 • 1 reviewer                [↗]
```

Timeline emphasizes flow and sequence. Useful for spotting:
- Burst patterns (lots of activity in one day)
- Gaps (quiet periods)
- Jira → PR correlation (feature marked done, PR merged same day)

### 7. Commit Handling Strategy

Commits are too numerous to display inline by default. They use an expandable aggregate pattern.

**Collapsed state (default):**

```
┌─ Commits (47) ─────────────────────────────────────────────────────────┐
│  47 commits across 4 PRs                                          [▸] │
└────────────────────────────────────────────────────────────────────────┘
```

**Expanded state (on click):**

```
┌─ Commits (47) ─────────────────────────────────────────────────────────┐
│  47 commits across 4 PRs                                          [▾] │
├────────────────────────────────────────────────────────────────────────┤
│  Jun 15 • 8 commits                                                    │
│    a1b2c3  Fix null check before dereference                   [↗]    │
│    d4e5f6  Add unit tests for auth handler                      [↗]    │
│    ... 6 more commits                                                  │
│                                                                        │
│  Jun 14 • 12 commits                                                   │
│    7g8h9i  Implement rate limiting middleware                  [↗]    │
│    ... 11 more commits                                                 │
│                                                                        │
│  Jun 13 • 15 commits                                                   │
│    j0k1l2  Refactor auth middleware                            [↗]    │
│    ... 14 more commits                                                 │
│                                                                        │
│  [View all commits on GitHub ↗]                                       │
└────────────────────────────────────────────────────────────────────────┘
```

**Per-commit row format:**
- Short SHA (7 characters)
- Truncated commit message (~50 characters)
- External link to commit on GitHub

**Behavior:**
- Click chevron or row to toggle expand/collapse
- State persisted in component local state (not URL)
- Timeline view shows commits grouped by day with same expand pattern
- "View all on GitHub" link opens filtered commit search

### 8. Active Work Section

Separate from shipped items, always visible regardless of view toggle.

```
┌─ Active Work ──────────────────────────────────────────────────────────┐
│                                                                        │
│  #55  Add two-factor authentication               [draft]    2d ago   │
│       owner/repo • +156 −12 • awaiting review               [↗]      │
│                                                                        │
│  PROJ-200  Review dashboard layout             In Progress            │
│            Task • assigned to Jane                             [↗]    │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

Active work shows:
- Open PRs (including drafts)
- Jira issues not in terminal states (Done, Closed, Cancelled)

This section answers: "What is Jane working on right now?" Independent of the shipped work view.

### 9. Navigation from People Table

Add a "View work items" action on each row in the People table:
- Clicking the action navigates to `/persons/:id?section=work-items`
- The PersonDetailPage opens with WorkItemsSection expanded and scrolled into view
- Status defaults to `completed` with the same time range as the People table

Alternatively: Row click already navigates to PersonDetailPage; the WorkItemsSection is visible by default.

### 10. Database Query Implementation

Add `work_items()` method to `AggregationQueries`:

```python
def work_items(
    self,
    person_id: str,
    status: Literal["active", "completed"],
    datasource: str | None,
    event_type: str | None,
    from_ts: datetime | None,
    to_ts: datetime | None,
    page: int,
    per_page: int,
) -> tuple[list[WorkItem], int]:
    ...
```

Query structure:
1. Resolve person identities: `SELECT source, external_id FROM person_identities WHERE person_id = ?`
2. Build base query on `raw_events` with `(source, actor) IN (identities)`
3. Apply status filters:
   - For `active`: `event_type IN ('pull_request', 'issue') AND data->>'state' NOT IN ('closed', 'merged')` (GitHub), or Jira status not in terminal states
   - For `completed`: `timestamp BETWEEN ? AND ?` + completion state filters
4. Apply optional datasource/event_type filters
5. Order by `timestamp DESC`
6. Apply pagination with `LIMIT ? OFFSET ?`
7. Count total for pagination

### 11. Response Model

```python
class WorkItemMetadata(BaseModel):
    additions: int | None = None
    deletions: int | None = None
    reviewers: list[str] | None = None
    issue_type: str | None = None
    story_points: int | None = None
    labels: list[str] | None = None
    pr_number: int | None = None  # for commits

class WorkItem(BaseModel):
    id: str
    datasource: str
    event_type: str
    external_id: str
    project: str
    title: str
    description: str | None
    status: str
    timestamp: datetime
    url: str
    metadata: WorkItemMetadata | None

class WorkItemsResponse(BaseModel):
    person_id: str
    status: str
    total: int
    page: int
    per_page: int
    items: list[WorkItem]
```

### 12. Frontend Hooks

Add `useWorkItems` hook:

```typescript
interface WorkItemsParams {
  personId: string;
  status: 'active' | 'completed';
  datasource?: string;
  eventType?: string;
  from?: string;
  to?: string;
  page?: number;
  perPage?: number;
}

function useWorkItems(params: WorkItemsParams) {
  // Returns { items, total, page, isLoading, error }
}
```

### 13. URL Parameters for Deep Linking

The PersonDetailPage accepts URL params for work items section state:
- `?section=work-items` — expand and scroll to work items
- `?view=grouped` — use grouped view (default)
- `?view=timeline` — use timeline view
- `?status=active` — show active work items (note: active work is now always visible)
- `?datasource=github` — filter to GitHub
- `?event_type=pull_request` — filter to PRs

These are readable from URL and applied on mount.

## Risks / Trade-offs

- **[Risk] Large result sets for prolific contributors** → Mitigation: pagination with reasonable default (20/page). Active items are bounded (a person typically has < 20 open PRs/issues).
- **[Risk] Active items becoming stale** → Mitigation: active items are re-fetched on each page load. Consider adding a refresh button in v2.
- **[Risk] Description truncation hiding critical info** → Mitigation: description expands on click; external link always available.
- **[Risk] Commit expansion adding UI complexity** → Mitigation: commits are collapsed by default; expansion is opt-in per user.
- **[Trade-off] No full-text search in v1** → Acceptable for v1; users can Ctrl+F in browser or use external search in GitHub/Jira.
- **[Trade-off] Two view modes increase implementation scope** → Acceptable; both views use the same API data, only rendering differs.

## Open Questions

- Should active work items show estimated time or due date for Jira issues? (May require additional Jira field mapping.)
- Should draft PRs be highlighted differently from regular open PRs? (Currently both are "active" with same badge color.)
