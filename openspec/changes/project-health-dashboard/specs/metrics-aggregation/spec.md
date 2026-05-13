## ADDED Requirements

### Requirement: Unified issue aggregation across systems
The system SHALL aggregate issues from GitHub and Jira into a unified view, treating them as equivalent entities for person-centric and project-centric metrics. Aggregation MUST normalize issue types to a common taxonomy (bug, feature, maintenance) using configurable per-project mappings.

#### Scenario: GitHub and Jira issues combined in a single count
- **WHEN** a project has 5 GitHub issues and 3 Jira issues opened in the selected timeframe
- **THEN** the "issues opened" metric reports 8 total, with the ability to drill down and see 5 from GitHub and 3 from Jira

#### Scenario: Issue type normalization across systems
- **WHEN** a GitHub issue has label "bug" and a Jira issue has type "Bug"
- **THEN** both are categorized as "bug" in the issue type breakdown metric

#### Scenario: Unmapped issue type handled gracefully
- **WHEN** a Jira issue has an issue type not present in the mapping configuration
- **THEN** it is categorized as "other" and still counted in the total

### Requirement: Per-person contribution aggregation
The system SHALL compute contribution metrics per person across all data sources, summing commits, PRs, LOC added/removed, and issues resolved regardless of which system they originate from.

#### Scenario: Person resolves issues in both GitHub and Jira
- **WHEN** a team member closes 2 GitHub issues and resolves 3 Jira issues in the selected timeframe
- **THEN** their "issues resolved" count is 5, with per-source breakdown available on drill-down

#### Scenario: Person identity mapping across systems
- **WHEN** a configured identity mapping links `github-user-a` to `jira-account-id-X`
- **THEN** all events from both identities are attributed to a single person in aggregated views

#### Scenario: Unmapped identities shown separately
- **WHEN** an identity mapping is not configured for a given person
- **THEN** their contributions are shown as separate rows per source (labeled "GitHub: username" and "Jira: accountId") in the per-person table

### Requirement: PR and commit aggregation
The system SHALL aggregate PR count, commit count, and LOC added/removed per project and per person from GitHub data (and future Launchpad data) within a given timeframe.

#### Scenario: PR count and LOC aggregated per project
- **WHEN** a project has 10 merged PRs in the last 30 days with total 500 additions and 200 deletions
- **THEN** the project metric shows 10 PRs, +500/-200 LOC

#### Scenario: PRs per team member across all projects
- **WHEN** the "people" view is selected for the last 90 days
- **THEN** each team member row shows total PRs and net LOC across all configured projects, sorted by PR count descending

### Requirement: Velocity metrics computation
The system SHALL compute cycle time (time from first commit to PR merge) and PR review turnaround (time from PR opened to first review) for all merged PRs in the selected timeframe.

#### Scenario: Cycle time calculated for a merged PR
- **WHEN** a PR received its first commit on day 1 and was merged on day 4
- **THEN** the cycle time is 3 days, and the PR contributes to the median and p50/p90 cycle time charts

#### Scenario: PR review turnaround calculated
- **WHEN** a PR was opened on Monday at 10:00 and received its first review on Tuesday at 10:00
- **THEN** the review turnaround is 24 hours, included in the turnaround distribution

### Requirement: PR size distribution
The system SHALL categorize PRs into size buckets (small: <100 LOC, medium: 100-500 LOC, large: >500 LOC) based on total additions + deletions and SHALL display the distribution for the selected timeframe.

#### Scenario: PR size buckets computed
- **WHEN** 20 PRs were merged with sizes: 5 small, 10 medium, 5 large
- **THEN** the size distribution chart shows 25% small, 50% medium, 25% large

### Requirement: Review distribution matrix
The system SHALL compute which team members review PRs from which authors, producing a review distribution matrix for the selected timeframe.

#### Scenario: Review relationships captured
- **WHEN** Alice reviewed 3 of Bob's PRs and 1 of Carol's PRs in the last 30 days
- **THEN** the review distribution matrix shows Alice as reviewer for Bob (3 reviews) and Carol (1 review)

### Requirement: Per-person review aggregation
The system SHALL compute per-person review activity: number of reviews, number of inline review comments, and comments-per-review ratio across all review states (APPROVED, CHANGES_REQUESTED, COMMENTED). Aggregation SHALL support time-series breakdown (reviews per time bucket) and reviewee breakdown (who the person reviewed, with counts).

#### Scenario: Reviews and comments per person computed
- **WHEN** Alice performed 8 reviews with 20 total inline comments in the last 30 days
- **THEN** her review metrics are: 8 reviews, 20 comments, 2.5 comments/review

#### Scenario: Review state breakdown available on drill-down
- **WHEN** Alice performed 5 APPROVED, 2 CHANGES_REQUESTED, and 1 COMMENTED reviews
- **THEN** the per-person Collaboration drill-down shows the breakdown by review state

#### Scenario: Reviewee breakdown
- **WHEN** Alice reviewed 3 of Bob's PRs and 2 of Carol's PRs
- **THEN** the per-person Collaboration drill-down shows "Reviews given: Bob (3), Carol (2)"

### Requirement: Time-series metric endpoints
The system SHALL expose `/ts` time-series variants for key aggregation endpoints, returning bucketed data points for the selected timeframe. Bucket size SHALL be auto-derived from the timeframe range: ≤7 days → daily, ≤90 days → weekly, ≤1 year → monthly, >1 year → quarterly.

#### Scenario: Weekly buckets for 90-day range
- **WHEN** `GET /api/metrics/contribution-volume/ts?from=2025-01-01&to=2025-03-31`
- **THEN** the response returns ~13 weekly data points, each with count for that week

#### Scenario: Daily buckets for 7-day range
- **WHEN** `GET /api/metrics/velocity/ts?from=2025-01-01&to=2025-01-07`
- **THEN** the response returns 7 daily data points for cycle time and review turnaround

#### Scenario: Sprint uses sprint duration for bucketing
- **WHEN** `GET /api/metrics/contribution-volume/ts?sprint_id=sprint-42` and the sprint is 14 days long
- **THEN** the response returns daily data points (since ≤7 days per bucket rule would produce daily for a 14-day range, falling under ≤90 days → weekly when treated as a date range)

### Requirement: Per-person time-series scoping
The time-series endpoints SHALL support an `actors[]` query parameter to scope bucketed data to specific individuals.

#### Scenario: One person's time-series
- **WHEN** `GET /api/metrics/contribution-volume/ts?from=2025-01-01&to=2025-03-31&actors=alice`
- **THEN** the response returns Alice's weekly contribution data points only

### Requirement: Internal vs external contribution ratio
The system SHALL classify PR authors and issue reporters as "internal" (listed in a configured team members list) or "external" and compute the ratio for the selected timeframe.

#### Scenario: Ratio calculated for mixed contributions
- **WHEN** in the last 30 days, 40 PRs were from internal members and 10 from external contributors
- **THEN** the ratio is reported as 80% internal / 20% external

### Requirement: Aggregation API endpoints
The system SHALL expose REST API endpoints for each metric, accepting query parameters for timeframe (start/end timestamps or sprint ID), project filter, and person filter. Time-series variants SHALL be exposed at `/ts` sub-paths for key metrics.

#### Scenario: Fetch contribution volume for a date range
- **WHEN** `GET /api/metrics/contribution-volume?from=2025-01-01&to=2025-01-31&projects=repo-a`
- **THEN** the response includes commit count, PR count, LOC added/removed, internal/external ratio, PRs per person, and issues opened/resolved for repo-a in January 2025

#### Scenario: Fetch contribution volume time-series
- **WHEN** `GET /api/metrics/contribution-volume/ts?from=2025-01-01&to=2025-03-31&projects=repo-a`
- **THEN** the response returns bucketed (weekly) data points with commit count, PR count, LOC, and issues opened/resolved per bucket for repo-a

#### Scenario: Fetch velocity metrics for a sprint
- **WHEN** `GET /api/metrics/velocity?sprint_id=sprint-42`
- **THEN** the response includes cycle time distribution and PR review turnaround for all PRs merged during sprint-42

#### Scenario: Fetch velocity time-series
- **WHEN** `GET /api/metrics/velocity/ts?from=2025-01-01&to=2025-03-31`
- **THEN** the response returns bucketed cycle time and PR review turnaround per period

#### Scenario: Fetch per-person review activity
- **WHEN** `GET /api/metrics/collaboration?from=2025-01-01&to=2025-03-31&actors=alice`
- **THEN** the response includes Alice's reviews given (count, comment count, comments/review ratio) with reviewee breakdown and review state breakdown

#### Scenario: Fetch per-person review time-series
- **WHEN** `GET /api/metrics/collaboration/ts?from=2025-01-01&to=2025-03-31&actors=alice`
- **THEN** the response returns bucketed review activity data points for Alice

#### Scenario: Fetch velocity time-series
- **WHEN** `GET /api/metrics/velocity/ts?from=2025-01-01&to=2025-03-31`
- **THEN** the response returns bucketed cycle time and PR review turnaround per period

#### Scenario: Fetch per-person review activity
- **WHEN** `GET /api/metrics/collaboration?from=2025-01-01&to=2025-03-31&actors=alice`
- **THEN** the response includes Alice's reviews given (count, comment count, comments/review ratio) with reviewee breakdown and review state breakdown

#### Scenario: Fetch per-person review time-series
- **WHEN** `GET /api/metrics/collaboration/ts?from=2025-01-01&to=2025-03-31&actors=alice`
- **THEN** the response returns bucketed review activity data points for Alice

### Requirement: Caching with invalidation
The system SHALL cache aggregation query results with a TTL of 5 minutes and SHALL invalidate all caches after each completed ingestion cycle.

#### Scenario: Cache hit returns fast response
- **WHEN** the same aggregation query is made twice within the TTL
- **THEN** the second request returns from cache without re-computing

#### Scenario: Cache invalidated after ingestion
- **WHEN** an ingestion cycle completes
- **THEN** all cached aggregation results are invalidated, and the next query for any metric recomputes from fresh `raw_events` data
