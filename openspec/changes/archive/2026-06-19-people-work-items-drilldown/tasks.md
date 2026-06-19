## 1. Work Items Backend — Query Layer

- [x] 1.1 Add `WorkItemMetadata` and `WorkItem` Pydantic models in `src/project_health/aggregation/models.py`
- [x] 1.2 Add `WorkItemsResponse` Pydantic model with pagination fields
- [x] 1.3 Add `work_items()` method to `AggregationQueries` — resolves person identities, queries `raw_events`, applies status/datasource/event_type filters, returns paginated results
- [x] 1.4 Implement active status filter logic: open PRs (`state=open`), open GitHub issues, Jira issues not in terminal states
- [x] 1.5 Implement completed status filter logic: merged PRs, closed GitHub issues, resolved Jira issues, within time range
- [x] 1.6 Extract title, description, URL from `raw_events.data` JSON field per event type
- [x] 1.7 Add `commits()` method to `AggregationQueries` — resolves person identities, queries commit events, grouped by day with pagination
- [x] 1.8 Add unit tests for `work_items()` — test active vs completed, datasource filter, pagination
- [x] 1.9 Add unit tests for `commits()` — test day grouping, pagination, commit metadata extraction

## 2. Work Items API Endpoints

- [x] 2.1 Add `GET /api/persons/{person_id}/work-items` route in `src/project_health/api/routes/persons.py`
- [x] 2.2 Parse query params: `status`, `datasource`, `event_type`, `from`, `to`, `page`, `per_page`
- [x] 2.3 Call `AggregationQueries.work_items()` and return `WorkItemsResponse`
- [x] 2.4 Add validation: require `from`/`to` when `status=completed`
- [x] 2.5 Add `GET /api/persons/{person_id}/commits` route — returns commits grouped by day with pagination
- [x] 2.6 Add OpenAPI response models and regenerate `frontend/src/api/types.ts`
- [x] 2.7 Add integration tests for work-items endpoint — test filtering, pagination, error cases
- [x] 2.8 Add integration tests for commits endpoint — test day grouping, pagination

## 3. Frontend Types and Hooks

- [x] 3.1 Run `openapi-typescript` to generate `WorkItem`, `WorkItemsResponse`, `Commit`, `CommitsResponse` types
- [x] 3.2 Add `workItems` method to `frontend/src/api/client.ts`
- [x] 3.3 Add `commits` method to `frontend/src/api/client.ts`
- [x] 3.4 Create `useWorkItems` hook in `frontend/src/hooks/useMetrics.ts` — accepts params, returns `{ items, total, page, isLoading, error }`
- [x] 3.5 Create `useCommits` hook — accepts params, returns `{ commits, total, page, isLoading, error }`
- [x] 3.6 Handle URL params in hooks: read `section`, `view`, `datasource`, `event_type` from URL

## 4. Work Item Card Component

- [x] 4.1 Create `WorkItemCard` component in `frontend/src/components/WorkItemCard.tsx`
- [x] 4.2 Render datasource badge (GH/Jira/LP icons)
- [x] 4.3 Render title, status badge, project/external ID, timestamp, external link
- [x] 4.4 Render truncated description with expand-on-click
- [x] 4.5 Render metadata chips (LOC for PRs, story points for Jira, issue type)
- [x] 4.6 Support compact mode for timeline view (reduced vertical padding)
- [x] 4.7 Add hover/focus states and accessible markup
- [x] 4.8 Add Storybook story for component (using unit tests instead - project doesn't use Storybook)

## 5. Commit List Component

- [x] 5.1 Create `CommitList` component in `frontend/src/components/CommitList.tsx`
- [x] 5.2 Collapsed state: show aggregate count ("47 commits across 4 PRs") with expand chevron
- [x] 5.3 Expanded state: fetch commits via `useCommits`, group by day
- [x] 5.4 Per-commit row: short SHA, truncated message, external link
- [x] 5.5 "View all commits on GitHub" footer link
- [x] 5.6 Loading skeleton for expanded state
- [x] 5.7 Track expanded/collapsed state in local component state

## 6. Grouped Work Items View

- [x] 6.1 Create `GroupedWorkItemsView` component in `frontend/src/components/GroupedWorkItemsView.tsx`
- [x] 6.2 Group items by datasource, then by event type
- [x] 6.3 Collapsible sections for each group (Jira Issues, Pull Requests, Commits)
- [x] 6.4 Each section shows count in header
- [x] 6.5 Use `WorkItemCard` for items, `CommitList` for commits section
- [x] 6.6 Persist collapse state per section in local state

## 7. Timeline Work Items View

- [x] 7.1 Create `TimelineWorkItemsView` component in `frontend/src/components/TimelineWorkItemsView.tsx`
- [x] 7.2 Sort all items by timestamp DESC
- [x] 7.3 Group by day with date headers ("Jun 15", "Jun 14")
- [x] 7.4 Render `WorkItemCard` in compact mode per item
- [x] 7.5 Render `CommitList` (collapsed by default) per day under commit count
- [x] 7.6 Visual timeline connector (vertical line) between days

## 8. View Toggle Component

- [x] 8.1 Create `ViewToggle` component in `frontend/src/components/ViewToggle.tsx`
- [x] 8.2 Two buttons: [Grouped] [Timeline]
- [x] 8.3 Active view highlighted
- [x] 8.4 Update URL param `?view=grouped` or `?view=timeline` on click
- [x] 8.5 Parent component reads URL param to determine which view to render

## 9. Active Work Section Component

- [x] 9.1 Create `ActiveWorkSection` component in `frontend/src/components/ActiveWorkSection.tsx`
- [x] 9.2 Fetch active work items via `useWorkItems({ status: 'active' })`
- [x] 9.3 Render list of `WorkItemCard` components
- [x] 9.4 Draft PRs show [draft] badge
- [x] 9.5 Loading skeleton, empty state ("No active work")
- [x] 9.6 Always visible, independent of view toggle

## 10. Work Items Section Component

- [x] 10.1 Create `WorkItemsSection` component in `frontend/src/components/WorkItemsSection.tsx`
- [x] 10.2 Section header with sprint/date label and `ViewToggle`
- [x] 10.3 Filter bar: datasource filter, event type filter
- [x] 10.4 Render `ActiveWorkSection` first (always visible)
- [x] 10.5 Render `GroupedWorkItemsView` or `TimelineWorkItemsView` based on URL param
- [x] 10.6 Pagination controls for completed items (not active)
- [x] 10.7 Section is collapsible; expand by default when `?section=work-items` in URL
- [x] 10.8 Scroll into view when `?section=work-items`

## 11. PersonDetailPage Integration

- [x] 11.1 Add `WorkItemsSection` to `PersonDetailPage` below charts
- [x] 11.2 Pass person ID and time range from page params
- [x] 11.3 Read URL params on mount: `section`, `view`, `datasource`, `event_type`
- [x] 11.4 Update navigation from People table to include work items context
- [x] 11.5 Ensure back navigation preserves filter state

## 12. Tests — Frontend

- [x] 12.1 Add unit tests for `WorkItemCard` — render all fields, status colors, links, compact mode
- [x] 12.2 Add unit tests for `CommitList` — collapsed/expanded states, day grouping, pagination
- [x] 12.3 Add unit tests for `GroupedWorkItemsView` — grouping logic, section collapse
- [x] 12.4 Add unit tests for `TimelineWorkItemsView` — day grouping, chronological order
- [x] 12.5 Add unit tests for `ViewToggle` — URL param updates, active state
- [x] 12.6 Add unit tests for `ActiveWorkSection` — fetch, empty state, draft badge
- [x] 12.7 Add tests for `useWorkItems` hook — params mapping, response handling
- [x] 12.8 Add tests for `useCommits` hook — day grouping, pagination

## 13. Integration & Polish

- [x] 13.1 End-to-end: navigate from People table → PersonDetailPage → work items section expands and scrolls
- [x] 13.2 Verify view toggle switches between grouped and timeline without data refetch
- [x] 13.3 Verify active work section shows current state (open PRs, in-progress Jira issues)
- [x] 13.4 Verify completed work items respect time range filter
- [x] 13.5 Verify commit expansion loads commits grouped by day with links
- [x] 13.6 Verify external links open in new tab
- [x] 13.7 Verify back navigation from PersonDetailPage preserves People table filters
- [x] 13.8 Run `ruff check`, `mypy`, `pytest` and `tsc --noEmit` / `vite build`; fix issues
