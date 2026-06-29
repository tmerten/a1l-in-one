## ADDED Requirements

### Requirement: Sprint definitions storage and retrieval
The system SHALL store sprint definitions from Jira (id, name, project, start_date, end_date, state) in a `sprints` table and expose them via a `GET /api/sprints` endpoint for use as timeframe references.

#### Scenario: Sprint list returned for the UI
- **WHEN** `GET /api/sprints?project=PROJ` is called
- **THEN** the response returns sprints for project PROJ ordered by end_date descending, including active sprints and completed sprints from the last 90 days

#### Scenario: Sprint data includes date bounds
- **WHEN** a sprint is returned from the API
- **THEN** each sprint object includes `start_date` and `end_date` fields that can be used directly as timeframe bounds for metric queries

### Requirement: Sprint as first-class timeframe
The system SHALL treat sprints as equivalent to custom date ranges in all metric aggregation queries, using sprint start and end dates as the time window.

#### Scenario: Metrics queried by sprint
- **WHEN** the aggregation API receives `sprint_id=sprint-42` as a timeframe parameter
- **THEN** it resolves the sprint's start and end dates from the `sprints` table and queries `raw_events` with `timestamp BETWEEN start AND end`

#### Scenario: Sprint and date range produce consistent results
- **WHEN** a sprint runs from Jan 6 to Jan 20 and a custom date range of the same dates is selected
- **THEN** both queries return identical metric values for all aggregation endpoints

### Requirement: Active sprint detection
The system SHALL identify the currently active sprint (if any) for each Jira project and surface it prominently in the sprint selector (e.g., "(active)" badge, default selection on dashboard load). When multiple Jira projects are configured and each has an active sprint, the picker SHALL group sprints by project, and the default selection SHALL be the active sprint of the first Jira project listed in the YAML `projects.jira` array.

#### Scenario: Active sprint is the default timeframe
- **WHEN** the dashboard loads and a sprint is currently active for the first configured Jira project
- **THEN** the sprint selector defaults to that active sprint, labeled "PROJ — Sprint 42 (active)"

#### Scenario: Multiple active sprints grouped by project
- **WHEN** two Jira projects are configured (`PROJ`, `BACK`) and each has an active sprint
- **THEN** the sprint picker dropdown groups sprints under their project key, each active one labeled "(active)"

#### Scenario: No active sprint falls back to relative preset
- **WHEN** the dashboard loads and no sprint is currently active for any configured Jira project
- **THEN** the timeframe defaults to "Last 30 days"

### Requirement: Sprint-aware metric aggregation
The system SHALL compute sprint-specific aggregations: sprint burndown (starts as simple committed-vs-completed), sprint velocity, and issues carried over to next sprint.

#### Scenario: Sprint burndown computed
- **WHEN** a sprint is selected that has Jira issues with story points
- **THEN** the dashboard displays a burndown showing committed story points vs completed story points, with carried-over count

#### Scenario: Sprint without story points
- **WHEN** a sprint has issues but no story points configured
- **THEN** the burndown falls back to issue count (committed vs completed issues) and displays a note "Story points not configured — showing issue count"
