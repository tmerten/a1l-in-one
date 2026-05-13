## ADDED Requirements

### Requirement: Tab-based navigation with shared header
The dashboard SHALL use a tab-based navigation with a persistent header containing the timeframe selector and project filter. Two tabs SHALL be available: "Projects" (default) and "People". Changing the timeframe or project filter SHALL update both pages.

#### Scenario: User switches between tabs
- **WHEN** the user selects "Last 30 days" and filters to "repo-a" on the Projects tab, then clicks the "People" tab
- **THEN** the People page loads with the same "Last 30 days" timeframe and "repo-a" project filter applied

#### Scenario: Timeframe change propagates across tabs
- **WHEN** the user changes the timeframe to "Last 90 days" on the People page, then switches to the Projects tab
- **THEN** the Projects page reflects the "Last 90 days" timeframe

### Requirement: Timeframe selector component
The dashboard SHALL include a single timeframe selector that supports Grafana-style relative presets (Last 7d, 30d, 90d, This month, This quarter, This year), an absolute date range picker (start → end calendar), and a sprint selector populated from available sprints. Changing the timeframe MUST trigger a refresh of all displayed metrics.

#### Scenario: User selects a relative preset
- **WHEN** the user selects "Last 30 days" from the timeframe selector
- **THEN** all metric components on the current page re-fetch data with `from = now - 30 days` and `to = now`

#### Scenario: User picks a custom date range
- **WHEN** the user selects January 1, 2025 as start date and January 31, 2025 as end date
- **THEN** all metric components on the current page re-fetch data with the custom range

#### Scenario: User selects a sprint
- **WHEN** the user picks "Sprint 42" from the sprint dropdown
- **THEN** all metric components re-fetch data bounded by Sprint 42's start and end dates, and the timeframe selector displays "Sprint 42 (Jan 6 – Jan 20, 2025)"

### Requirement: Project filter
The dashboard SHALL include a multi-select project filter in the shared header that allows users to view metrics for one, several, or all configured projects.

#### Scenario: Single project selected
- **WHEN** the user selects only "repo-a" in the project filter
- **THEN** all metrics show data scoped to repo-a only

#### Scenario: Multiple projects selected
- **WHEN** the user selects "repo-a" and "repo-b"
- **THEN** all metrics show combined data from both projects

#### Scenario: People page scoped by project filter
- **WHEN** the user selects only "repo-a" on the People page
- **THEN** each person's row shows only their contributions to repo-a, and the summary stats reflect the scoped view

### Requirement: Projects page — metric sections
The Projects page SHALL display the four metric sections scoped to the selected timeframe and project filter: Contribution Volume, Velocity & Throughput, Quality & Composition, and Collaboration. When a sprint is selected, a sprint burndown chart SHALL appear above the metric sections.

### Requirement: People page — summary stats
The People page SHALL display a thin summary row above the people table showing: number of contributors, median PRs, median issues resolved, and median cycle time — all scoped to the selected timeframe and project filter.

#### Scenario: Summary stats render with data
- **WHEN** the People page loads with 8 contributors, median 12 PRs, median 5 issues resolved, median 2.1 days cycle time
- **THEN** the summary row displays all four values

### Requirement: People page — ranked table
The People page SHALL display a sortable, ranked table of all contributors with columns: Name, Commits, PRs, LOC, Issues Resolved, Median Cycle Time, Reviews Given, Comments, Comments/Review. Each numeric cell SHALL include an inline background bar proportional to the column's maximum value for visual comparison.

#### Scenario: People table renders with inline bars
- **WHEN** Alice has 20 PRs and Bob has 5 PRs in the selected timeframe
- **THEN** Alice's PR cell background bar is 100% width, Bob's is 25% width

#### Scenario: People table is sortable
- **WHEN** the user clicks the "PRs" column header
- **THEN** rows reorder from highest to lowest PR count, and clicking again reverses the order

#### Scenario: Unmapped identities shown separately
- **WHEN** identity mapping is not configured for a person appearing in GitHub and Jira
- **THEN** they appear as separate rows labeled by source ("GH: username", "Jira: accountId")

### Requirement: People table — outlier color encoding
The People table SHALL support toggleable color encoding that highlights cells relative to the team median. Above-median values SHALL be shaded green, below-median values red.

#### Scenario: Outlier color encoding is enabled
- **WHEN** the user enables color encoding in settings and the team median PRs is 10
- **THEN** a cell with 25 PRs is shaded green, a cell with 3 PRs is shaded red

#### Scenario: Color encoding can be disabled
- **WHEN** the user disables color encoding in settings
- **THEN** all cells render without color highlighting

### Requirement: People table — sparklines
The People table SHALL include a sparkline column that shows a tiny time-series chart for a configurable primary metric (default: resolved work) over the selected timeframe, auto-bucketed (≤7 days → daily, ≤90 days → weekly, etc.).

#### Scenario: Sparkline renders for each person
- **WHEN** the People table loads with a 90-day timeframe
- **THEN** each person's row shows a sparkline with ~12-13 weekly data points for their resolved work trend

### Requirement: People page — per-person drill-down
Clicking a person row in the People table SHALL filter all metric sections below the table to show data for that specific person. A "Clear" button or deselecting the row SHALL return to the full team view.

#### Scenario: Person drill-down filters all sections
- **WHEN** the user clicks Alice's row in the People table
- **THEN** the Contribution Volume, Velocity & Throughput, Quality & Composition, and Collaboration sections below the table all re-render with data scoped to Alice only

#### Scenario: Problematic data in drill-down
- **WHEN** a person is selected and the Collaboration section loads with Alice's review data
- **THEN** the Collaboration section shows who Alice reviewed (with time-series trend) instead of the full team review matrix

#### Scenario: Clear returns to team view
- **WHEN** the user clicks "Clear" or deselects Alice's row
- **THEN** all metric sections return to the full team view

### Requirement: Contribution volume section
The dashboard SHALL display a "Contribution Volume" section containing charts for commit count, PR count with LOC delta, internal vs external ratio, and issues opened vs resolved — all scoped to the selected timeframe and project filter. On the Projects page, the section SHALL include a per-project breakdown. On the People page with a person selected, it SHALL show that person's contribution across all selected projects.

#### Scenario: Contribution volume section renders with data
- **WHEN** the dashboard loads with valid data for the selected timeframe
- **THEN** the contribution volume section shows all charts, each populated with data from the `/api/metrics/contribution-volume` endpoint

#### Scenario: No data in timeframe
- **WHEN** the selected timeframe has no events (e.g., future date range)
- **THEN** each chart displays an "No data for this period" empty state

### Requirement: Velocity and throughput section
The dashboard SHALL display a "Velocity & Throughput" section with cycle time distribution (p50, p90, median) and PR review turnaround distribution for merged PRs in the selected timeframe. On the People page with a person selected, it SHALL show that person's individual velocity.

#### Scenario: Cycle time chart shows distribution
- **WHEN** 50 PRs were merged in the selected timeframe with varying cycle times
- **THEN** the cycle time chart displays a histogram or box plot with p50 and p90 indicators

### Requirement: Quality and composition section
The dashboard SHALL display a "Quality & Composition" section with an issue type breakdown chart (bug / feature / maintenance / other) and a PR size distribution chart (small / medium / large). On the People page with a person selected, it SHALL show that person's personal composition.

#### Scenario: Issue type breakdown renders
- **WHEN** the selected timeframe has 60% features, 30% bugs, 10% maintenance across all systems
- **THEN** the breakdown chart shows those proportions, with hover/drill-down showing per-source breakdown within each type

### Requirement: Collaboration section
On the Projects page, the Collaboration section SHALL display a review distribution matrix or chord diagram showing who reviews whose PRs. On the People page with a person selected, it SHALL display a time-series of reviews given by that person, broken out by reviewee and review state (approved, changes_requested, commented).

#### Scenario: Review matrix shows reviewer-author pairs
- **WHEN** PR reviews occurred between team members in the selected timeframe
- **THEN** the matrix shows each reviewer-author pair with review count, enabling identification of review patterns and potential silos

#### Scenario: Per-person reviews given with time-series
- **WHEN** Alice is selected on the People page and she reviewed 5 PRs in the last 90 days
- **THEN** the Collaboration section shows a time-series chart of her reviews over the timeframe with a reviewee breakdown (e.g., "Bob: 3, Carol: 2") and reviews/comments counts

### Requirement: Drill-down to per-system raw data
Each aggregated metric SHALL support drill-down to show per-source breakdowns (GitHub vs Jira contribution to the total). Clicking a data point or row MUST expand to show source-level detail.

#### Scenario: Drill into issues opened by source
- **WHEN** the user clicks on "12 issues opened" in the contribution volume section
- **THEN** a breakdown appears showing "GitHub: 7, Jira: 5" with a link to view the raw event list

#### Scenario: Drill into per-source issue type breakdown
- **WHEN** the user clicks a "bug" segment in the issue type breakdown chart
- **THEN** the breakdown shows how many bugs came from GitHub vs Jira, with system-native labels (e.g., "GitHub label: bug", "Jira type: Bug")

### Requirement: Loading and error states
Every metric component SHALL handle loading, error, and empty states gracefully.

#### Scenario: Metric data is loading
- **WHEN** a metric component is fetching data from the API
- **THEN** it displays a skeleton placeholder or spinner until data arrives

#### Scenario: API returns an error
- **WHEN** a metric endpoint returns a 5xx error
- **THEN** the component displays an error message with a retry button, without affecting other metric components

### Requirement: Settings and configuration panel
The dashboard SHALL include a settings panel where the user can configure which metric sections are visible (show/hide toggle per section), toggle outlier color encoding on/off, configure the primary metric for the People table sparkline column, and persist layout preferences locally.

#### Scenario: User hides a metric section
- **WHEN** the user toggles off the "Collaboration" section in settings
- **THEN** the collaboration section is hidden from both the Projects and People pages, and the preference is saved locally

#### Scenario: User toggles outlier color encoding
- **WHEN** the user enables outlier color encoding in settings
- **THEN** the People table cells are color-coded relative to the team median

#### Scenario: Settings persist across sessions
- **WHEN** the user closes and reopens the dashboard
- **THEN** their section visibility, color encoding, and sparkline preferences are restored from localStorage
