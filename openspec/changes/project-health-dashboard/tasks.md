## 1. Foundation & Data Layer

- [ ] 1.1 Create project module structure (ingestion, aggregation, dashboard)
- [ ] 1.2 Define `raw_events` table schema with UUID PK, source, event_type, external_id, timestamp, ingested_at, actor, project, data (JSONB)
- [ ] 1.3 Create indexes on `raw_events`: `(source, timestamp)`, `actor`, `project`
- [ ] 1.4 Define `sprints` table schema with id, name, project, start_date, end_date, state
- [ ] 1.5 Define configuration schema for providers (type, credentials, projects/repos, mapping configs)
- [ ] 1.6 Define identity mapping schema (linking identities across GitHub, Jira, and future systems)

## 2. Provider Interface & Configuration

- [ ] 2.1 Define `DataSourceProvider` interface with `fetchCommits`, `fetchPullRequests`, `fetchPullRequestReviews`, `fetchIssues`, `fetchSprints`, `healthCheck`
- [ ] 2.2 Define typed event models (`RawCommitEvent`, `RawPREvent`, `RawReviewEvent`, `RawIssueEvent`, `SprintDefinition`)
- [ ] 2.3 Implement `DataSourceRegistry` that loads providers from configuration
- [ ] 2.4 Implement configuration loader (YAML/JSON file or env-based) for provider credentials and settings

## 3. GitHub Provider

- [ ] 3.1 Implement GitHub API client with authenticated requests (token-based)
- [ ] 3.2 Implement `fetchCommits(since)` — query commits endpoint, paginate, return `RawCommitEvent[]`
- [ ] 3.3 Implement `fetchPullRequests(since)` — query PRs endpoint with state, paginate, include `additions`, `deletions` in data payload
- [ ] 3.4 Implement `fetchPullRequestReviews(since)` — query PR reviews endpoint, paginate, include `review_state` (APPROVED/CHANGES_REQUESTED/COMMENTED) and `comment_count` in data payload
- [ ] 3.5 Implement `fetchIssues(since)` — query issues endpoint excluding PRs, paginate, include labels and state in data payload
- [ ] 3.6 Implement `healthCheck()` — verify API token validity and repository access
- [ ] 3.7 Implement `fetchSprints()` returning empty (GitHub has no sprints)
- [ ] 3.8 Handle GitHub API rate limits with retry-after headers

## 4. Jira Provider

- [ ] 4.1 Implement Jira API client with authenticated requests (basic auth or OAuth)
- [ ] 4.2 Implement `fetchIssues(since)` — query JQL with updated >= since, paginate, include issue_type, story_points, status, labels in data payload
- [ ] 4.3 Implement `fetchSprints()` — query board sprints endpoint, return `SprintDefinition[]`
- [ ] 4.4 Implement `healthCheck()` — verify API credentials and project/board access
- [ ] 4.5 Implement `fetchCommits()` returning empty (Jira has no commits)
- [ ] 4.6 Implement `fetchPullRequests()` returning empty (Jira has no PRs)
- [ ] 4.7 Implement `fetchPullRequestReviews()` returning empty (Jira has no PR reviews)

## 5. Ingestion Scheduler

- [ ] 5.1 Implement incremental ingestion logic: determine `since` from the most recent `ingested_at` per source+event_type
- [ ] 5.2 Implement backfill logic: when no prior events exist, fetch from configurable lookback window (default 90 days)
- [ ] 5.3 Implement deduplication: on `external_id` conflict for same source+event_type, upsert (UPDATE existing)
- [ ] 5.4 Implement scheduler loop that triggers all configured providers on a configurable interval (default 15 min)
- [ ] 5.5 Implement per-provider error isolation — one provider failing does not halt others
- [ ] 5.6 Implement retry logic with exponential backoff (3 attempts) for transient API failures
- [ ] 5.7 Add structured logging for ingestion runs (start, success, failure per provider+event_type)

## 6. Sprint Storage & API

- [ ] 6.1 Implement sprint upsert logic from Jira provider output into `sprints` table
- [ ] 6.2 Implement `GET /api/sprints?project=<key>` endpoint returning sprints ordered by end_date desc
- [ ] 6.3 Add active sprint detection and "(active)" flag in API response

## 7. Aggregation Layer — Core

- [ ] 7.1 Implement timeframe resolver — normalize `{date_range}` and `{sprint_id}` into start/end timestamps
- [ ] 7.2 Implement issue type normalizer — map GitHub labels and Jira issue types to `bug | feature | maintenance | other` using configurable per-project mapping
- [ ] 7.3 Implement person identity resolver — apply identity mapping to collapse multi-system identities into a single person identifier
- [ ] 7.4 Implement PR size classifier — categorize PRs as small (<100 LOC), medium (100-500), large (>500) based on additions+deletions
- [ ] 7.5 Implement internal/external classifier — classify actors based on configured team members list
- [ ] 7.6 Implement time-series bucket generator — auto-derive bucket size from timeframe range: ≤7 days → daily, ≤90 days → weekly, ≤1 year → monthly, >1 year → quarterly

## 8. Aggregation Layer — Metrics

- [ ] 8.1 Compute commit count per project and per person for a given timeframe
- [ ] 8.2 Compute PR count with LOC added/removed per project and per person
- [ ] 8.3 Compute issues opened vs resolved per project and per person (unified across GitHub + Jira)
- [ ] 8.4 Compute internal vs external contribution ratio
- [ ] 8.5 Compute cycle time: for each merged PR, time from earliest associated commit to merge date; produce median, p50, p90
- [ ] 8.6 Compute PR review turnaround: for each merged PR, time from opened to first review; produce median, p50, p90
- [ ] 8.7 Compute issue type breakdown (bug / feature / maintenance / other) with unified counts
- [ ] 8.8 Compute PR size distribution (small / medium / large counts and percentages)
- [ ] 8.9 Compute review distribution matrix: for each reviewer, count reviews per author
- [ ] 8.10 Compute per-person review activity: reviews count, inline comment count, comments-per-review ratio, with review state breakdown (APPROVED/CHANGES_REQUESTED/COMMENTED)
- [ ] 8.11 Compute per-person reviewee breakdown: who this person reviewed, with counts per reviewee

## 9. Aggregation API Endpoints

- [ ] 9.1 Implement `GET /api/metrics/contribution-volume` — returns commits, PRs+LOC, issues opened/resolved, internal/external ratio
- [ ] 9.2 Implement `GET /api/metrics/velocity` — returns cycle time and PR review turnaround distributions
- [ ] 9.3 Implement `GET /api/metrics/composition` — returns issue type breakdown and PR size distribution
- [ ] 9.4 Implement `GET /api/metrics/collaboration` — returns review distribution matrix, and per-person review activity when `actors[]` is set
- [ ] 9.5 Implement `GET /api/metrics/sprint-burndown` — returns sprint burndown data (committed vs completed, carried over)
- [ ] 9.6 Support common query params across all endpoints: `from`, `to`, `sprint_id`, `projects[]`, `actors[]`
- [ ] 9.7 Support per-source breakdown in responses (show total + per-source detail for drill-down)

## 10. Aggregation API — Time-Series Endpoints

- [ ] 10.1 Implement `GET /api/metrics/contribution-volume/ts` — returns bucketed commit count, PR count+LOC, issues opened/resolved per time bucket
- [ ] 10.2 Implement `GET /api/metrics/velocity/ts` — returns bucketed cycle time and PR review turnaround per time bucket
- [ ] 10.3 Implement `GET /api/metrics/collaboration/ts` — returns bucketed review activity per person when `actors[]` is set
- [ ] 10.4 Support `actors[]` param on all `/ts` endpoints to scope bucketed data to specific individuals
- [ ] 10.5 Auto-bucketing logic shared across all `/ts` endpoints using timeframe → bucket resolver (7.6)

## 11. Aggregation Layer — Caching

- [ ] 11.1 Implement cache key generation from query parameters (timeframe + filters)
- [ ] 11.2 Implement TTL-based cache store (in-memory for v1) with 5-minute TTL
- [ ] 11.3 Implement cache invalidation triggered after each successful ingestion cycle
- [ ] 11.4 Add cache hit/miss metrics to logging

## 12. Dashboard — Shell & Shared Header

- [ ] 12.1 Create dashboard page shell with persistent header and tab-based navigation (Projects | People)
- [ ] 12.2 Implement shared timeframe state that persists across tab switches
- [ ] 12.3 Implement relative timeframe presets (Last 7d, 30d, 90d, This month, This quarter, This year)
- [ ] 12.4 Implement absolute date range picker (start date → end date calendar inputs)
- [ ] 12.5 Implement sprint picker dropdown populated from `GET /api/sprints`
- [ ] 12.6 Display active sprint prominently with "(active)" badge in sprint picker
- [ ] 12.7 Default timeframe: active sprint if available, otherwise "Last 30 days"
- [ ] 12.8 Implement project multi-select filter fetching available projects from API
- [ ] 12.9 Wire filter changes to trigger metric re-fetches on the active page

## 13. Dashboard — Projects Page

- [ ] 13.1 Create Projects page layout with SprintBurndown (when sprint selected) and four metric sections
- [ ] 13.2 Implement sprint burndown chart (committed-vs-completed with carried-over indicator)

### 13a. Contribution Volume Section

- [ ] 13a.1 Implement commit count chart (bar/line chart over timeframe)
- [ ] 13a.2 Implement PR count chart with LOC added/removed bars (stacked positive/negative)
- [ ] 13a.3 Implement internal vs external ratio display (pie or donut chart)
- [ ] 13a.4 Implement per-project contribution table
- [ ] 13a.5 Implement issues opened vs resolved chart (grouped bar: opened + resolved per period)

### 13b. Velocity & Throughput Section

- [ ] 13b.1 Implement cycle time distribution chart (histogram or box plot with p50/p90 markers)
- [ ] 13b.2 Implement PR review turnaround distribution chart (histogram with p50/p90 markers)

### 13c. Quality & Composition Section

- [ ] 13c.1 Implement issue type breakdown chart (stacked bar or donut: bug / feature / maintenance / other)
- [ ] 13c.2 Implement per-source hover breakdown on issue type chart (show GitHub vs Jira within each type)
- [ ] 13c.3 Implement PR size distribution chart (bar chart: small / medium / large with counts and percentages)

### 13d. Collaboration Section

- [ ] 13d.1 Implement review distribution matrix (table or heatmap: reviewers as rows, authors as columns, counts as cells)

## 14. Dashboard — People Page

- [ ] 14.1 Create People page layout with summary stats row, people table, and per-person metric sections below
- [ ] 14.2 Implement summary stats row: contributor count, median PRs, median issues resolved, median cycle time
- [ ] 14.3 Implement selected-person state — clicking a row filters all sections below, "Clear" deselects

### 14a. People Table

- [ ] 14a.1 Implement sortable people table with columns: Name, Commits, PRs, LOC, Issues Resolved, Median Cycle Time, Reviews, Comments, Comments/Review
- [ ] 14a.2 Implement inline background bars in numeric cells proportional to column max
- [ ] 14a.3 Implement sparkline column showing time-series for configured primary metric using `/ts` endpoint
- [ ] 14a.4 Implement outlier color encoding: shade cells green (above team median) or red (below team median)
- [ ] 14a.5 Handle unmapped identities (show separate rows per source labeled "GH: username", "Jira: accountId")

### 14b. Per-Person Drill-Down Sections

- [ ] 14b.1 Implement per-person Contribution Volume section scoped to selected person
- [ ] 14b.2 Implement per-person Velocity & Throughput section scoped to selected person
- [ ] 14b.3 Implement per-person Quality & Composition section scoped to selected person
- [ ] 14b.4 Implement per-person Collaboration section showing reviews given with reviewee breakdown and time-series trend
- [ ] 14b.5 Implement review state breakdown in per-person Collaboration drill-down (APPROVED/CHANGES_REQUESTED/COMMENTED)

## 15. Dashboard — Drill-down & Raw Data

- [ ] 15.1 Implement drill-down on issue counts: click to expand per-source breakdown (GitHub vs Jira)
- [ ] 15.2 Implement drill-down on issue type segments: show source-native labels alongside normalized type
- [ ] 15.3 Implement raw event list view: filtered table showing raw_events rows for a given drill-down selection

## 16. Dashboard — Loading, Error & Empty States

- [ ] 16.1 Implement skeleton/spinner loading state for each metric component
- [ ] 16.2 Implement error state with error message and retry button per component
- [ ] 16.3 Implement empty state ("No data for this period") per component and for People table
- [ ] 16.4 Ensure error in one component does not affect rendering of other components

## 17. Dashboard — Settings Panel

- [ ] 17.1 Implement settings panel with show/hide toggles for each metric section (shared across both pages)
- [ ] 17.2 Implement outlier color encoding toggle (on/off)
- [ ] 17.3 Implement sparkline primary metric selector (choose which metric drives the People table sparkline column)
- [ ] 17.4 Persist layout preferences locally (localStorage)

## 18. Integration & Polish

- [ ] 18.1 Add sprint burndown fallback message when story points are unavailable ("Story points not configured — showing issue count")
- [ ] 18.2 End-to-end integration test: scheduled ingestion → data stored → API returns metrics → dashboard renders
- [ ] 18.3 Test People page drill-down flow: select person → sections re-render scoped → clear returns to team view
- [ ] 18.4 Document provider interface and configuration format for future Launchpad integration
- [ ] 18.5 Run lint and typecheck, fix any issues
