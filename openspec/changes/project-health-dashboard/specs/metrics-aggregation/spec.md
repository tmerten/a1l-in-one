## ADDED Requirements

### Requirement: Unified issue aggregation across systems
The system SHALL aggregate issues from GitHub and Jira into a unified view, treating them as equivalent entities for person-centric and project-centric metrics. Aggregation MUST normalize issue types to a common taxonomy (`bug | feature | maintenance | other`) using configurable per-source mappings from the YAML `issue_type_mapping` section.

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
The system SHALL compute contribution metrics per person across all data sources, summing commits, PRs, additions, deletions, and issues resolved regardless of which system they originate from. Identities are collapsed into a single person by `LEFT JOIN` to `person_identities`; unmapped identities still appear, labeled by source.

#### Scenario: Person resolves issues in both GitHub and Jira
- **WHEN** a team member closes 2 GitHub issues and resolves 3 Jira issues in the selected timeframe
- **THEN** their "issues resolved" count is 5, with per-source breakdown available on drill-down

#### Scenario: Person identity mapping across systems
- **WHEN** the YAML team list links `github: jdoe` and `jira: 557058:abc-123` to the same person
- **THEN** all events from both identities are attributed to a single person in aggregated views

#### Scenario: Unmapped identities shown separately
- **WHEN** an identity from `raw_events` has no matching row in `person_identities` linked to a person
- **THEN** their contributions are shown as separate rows per source, labeled `GH: <username>` or `Jira: <accountId>`, in the per-person table

### Requirement: PR aggregation — merged PRs only, with separate additions and deletions
The system SHALL aggregate PR count and LOC (`additions`, `deletions`) per project and per person from merged PRs only. Closed-unmerged PRs SHALL be excluded from all v1 visible metrics. Additions and deletions SHALL be reported separately and rendered as `+N / −M` in person tables.

#### Scenario: Closed-unmerged PR excluded
- **WHEN** a PR was closed without being merged in the selected timeframe
- **THEN** it does not contribute to PR count, LOC, cycle time, or any other human metric

#### Scenario: PR LOC aggregated per project
- **WHEN** a project has 10 merged PRs in the last 30 days with total `additions = 500` and `deletions = 200`
- **THEN** the project metric shows 10 PRs, `+500 / −200`

#### Scenario: PRs per team member across all projects
- **WHEN** the People view is selected for the last 90 days
- **THEN** each team member row shows total merged PRs and `+N / −M` LOC across all configured projects, sortable by either column

### Requirement: Commit aggregation excludes squash-merge commits on main
The system SHALL compute commit count per person from commits associated with merged PRs (commits *in* a PR's history), not from traversal of the default branch. Squash-merge commits on `main` SHALL be ignored as a separate event to prevent double-counting.

#### Scenario: Squash-merge does not double-count
- **WHEN** a PR with 8 commits is merged via squash, producing 1 commit on `main`
- **THEN** the author's commit count for that PR is 8 (the PR's commits), not 9 (PR + squash)

### Requirement: Bot identities filtered from human metrics
The system SHALL filter actors listed in the YAML `bots` configuration out of all human metric queries (commits, PRs, LOC, issues, reviews). Bot events remain in `raw_events` for future analysis but never appear in v1 dashboard responses.

#### Scenario: Dependabot PR excluded from PR counts
- **WHEN** Dependabot opens 5 PRs in the selected timeframe and is listed in `bots.github`
- **THEN** the PR count metric does not include these 5 PRs in any per-person or per-project response

### Requirement: Co-authored commits credit primary author only
The system SHALL credit only the primary author of a commit in all v1 metrics. `Co-authored-by` trailers SHALL be preserved in `raw_events.data` for potential v2 use, but they SHALL NOT contribute to per-person counts in v1.

#### Scenario: Co-authored commit credits primary author
- **WHEN** a commit has author Alice and a `Co-authored-by` trailer for Bob
- **THEN** Alice's commit count increases by 1; Bob's does not

### Requirement: Velocity metrics — cycle time as PR opened → merged
The system SHALL compute cycle time as the duration from PR `created_at` to `merged_at` for all merged PRs in the selected timeframe. The earlier "first commit → merge" definition is explicitly replaced. PR review turnaround SHALL be computed as the duration from `PR.created_at` to the first non-author review.

#### Scenario: Cycle time calculated for a merged PR
- **WHEN** a PR is opened on Monday 09:00 and merged on Thursday 09:00
- **THEN** the cycle time is 72 hours, and the PR contributes to the median and p50/p90 cycle time distributions

#### Scenario: PR review turnaround calculated
- **WHEN** a PR was opened on Monday at 10:00 and received its first non-author review on Tuesday at 10:00
- **THEN** the review turnaround is 24 hours, included in the turnaround distribution

#### Scenario: Drafts are not subtracted in v1
- **WHEN** a PR is created as a draft and later marked ready for review
- **THEN** cycle time uses `created_at` (the draft creation time), not the `ready_for_review` timestamp

### Requirement: PR size buckets exclude generated and vendored files
The system SHALL categorize PRs into size buckets (`small <100`, `medium 100–500`, `large >500`) using `linguist_filtered_additions + linguist_filtered_deletions` from `raw_events.data` — i.e., excluding files marked `linguist-generated` or `linguist-vendored` in `.gitattributes`.

#### Scenario: Lockfile-only PR is not large
- **WHEN** a PR consists of a 2000-line `package-lock.json` update only
- **THEN** the filtered LOC is 0 and the PR is bucketed as `small` (or excluded from the count if filtered LOC is 0)

#### Scenario: PR size buckets computed
- **WHEN** 20 merged PRs have filtered LOC of: 5 small, 10 medium, 5 large
- **THEN** the size distribution shows 25% small, 50% medium, 25% large

### Requirement: Review distribution matrix
The system SHALL compute which team members review PRs from which authors, producing a review distribution matrix for the selected timeframe.

#### Scenario: Review relationships captured
- **WHEN** Alice reviewed 3 of Bob's PRs and 1 of Carol's PRs in the last 30 days
- **THEN** the review distribution matrix shows Alice as reviewer for Bob (3) and Carol (1)

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
- **WHEN** `GET /api/metrics/contribution-volume/ts?from=2026-01-01&to=2026-03-31`
- **THEN** the response returns ~13 weekly data points, each with counts for that week

#### Scenario: Daily buckets for 7-day range
- **WHEN** `GET /api/metrics/velocity/ts?from=2026-01-01&to=2026-01-07`
- **THEN** the response returns 7 daily data points for cycle time and review turnaround

### Requirement: Per-person time-series scoping
The time-series endpoints SHALL support an `actors[]` query parameter to scope bucketed data to specific individuals.

#### Scenario: One person's time-series
- **WHEN** `GET /api/metrics/contribution-volume/ts?from=2026-01-01&to=2026-03-31&actors=alice`
- **THEN** the response returns Alice's weekly contribution data points only

### Requirement: Internal vs external contribution ratio
The system SHALL classify PR authors and issue reporters as "internal" (resolved person present in the YAML `team` list under any source identity) or "external" (everyone else) and compute the ratio for the selected timeframe.

#### Scenario: Ratio calculated for mixed contributions
- **WHEN** in the last 30 days, 40 merged PRs were authored by internal team members and 10 by external contributors
- **THEN** the ratio is reported as 80% internal / 20% external

### Requirement: Aggregation API endpoints
The system SHALL expose REST API endpoints for each metric, accepting query parameters for timeframe (`from`/`to` or `sprint_id`), project filter (`projects[]`), and person filter (`actors[]`). Time-series variants SHALL be exposed at `/ts` sub-paths for key metrics. Responses SHALL include per-source breakdown alongside aggregated totals for drill-down.

#### Scenario: Fetch contribution volume for a date range
- **WHEN** `GET /api/metrics/contribution-volume?from=2026-01-01&to=2026-01-31&projects=repo-a`
- **THEN** the response includes commit count, merged-PR count, `+additions / −deletions`, internal/external ratio, PRs per person, and issues opened/resolved for repo-a in January 2026

#### Scenario: Fetch velocity metrics for a sprint
- **WHEN** `GET /api/metrics/velocity?sprint_id=sprint-42`
- **THEN** the response includes cycle time distribution and PR review turnaround for all PRs merged during sprint-42

#### Scenario: Fetch per-person review activity
- **WHEN** `GET /api/metrics/collaboration?from=2026-01-01&to=2026-03-31&actors=alice`
- **THEN** the response includes Alice's reviews given (count, comment count, comments/review ratio) with reviewee breakdown and review state breakdown

### Requirement: Per-source TTL cache with per-source invalidation
The system SHALL cache aggregation query results in memory with a 15-minute TTL. Cache keys include the set of sources involved in the query. When an ingestion run completes for a given source, only cache entries whose source set includes that source SHALL be invalidated.

#### Scenario: Cache hit returns fast response
- **WHEN** the same aggregation query is made twice within the TTL
- **THEN** the second request returns from cache without re-computing

#### Scenario: GitHub ingestion does not invalidate Jira-only cache
- **WHEN** a Jira-only query (e.g., issues filtered to Jira projects) has been cached, and a GitHub ingestion run completes
- **THEN** the cached Jira-only result remains valid; only entries whose source set includes GitHub are evicted

#### Scenario: Source-relevant cache invalidated after ingestion
- **WHEN** a GitHub ingestion cycle completes
- **THEN** cache entries whose source set includes GitHub are invalidated; the next matching query recomputes from fresh `raw_events`
