## ADDED Requirements

### Requirement: Extensible data source provider interface
The system SHALL define a `DataSourceProvider` interface that each data source (GitHub, Jira, future Launchpad) implements. Each provider MUST support a health check and return typed event arrays for the event types it supports, including PR reviews as a first-class event type. Unsupported event types return empty arrays.

#### Scenario: Provider returns events for a supported type
- **WHEN** the GitHub provider is invoked with `fetch_pull_requests(since)` for a valid repository
- **THEN** it returns an array of `RawPREvent` objects, each with `external_id`, `timestamp`, `actor`, `project`, and source-specific data

#### Scenario: Provider returns review events
- **WHEN** the GitHub provider is invoked with `fetch_pull_request_reviews(since)` for a valid repository
- **THEN** it returns an array of `RawReviewEvent` objects, each with `external_id`, `timestamp`, `actor` (the reviewer), `project`, and a data payload containing `review_state` (APPROVED | CHANGES_REQUESTED | COMMENTED) and `comment_count`

#### Scenario: Provider returns empty for unsupported event type
- **WHEN** the GitHub provider is invoked with `fetch_sprints()`
- **THEN** it returns an empty array

#### Scenario: Provider health check fails
- **WHEN** a provider's credentials are invalid or the upstream API is unreachable
- **THEN** `health_check()` returns `false` and the scheduler logs the failure without halting other providers

### Requirement: YAML-driven configuration
The system SHALL load all configuration from a single YAML file (default path `./project-health.yaml`, overridable via `--config`). The YAML declares team members (with their GitHub and Jira identities), projects (GitHub repos and Jira project/board pairs), credentials (with `${ENV_VAR}` references), ingestion settings, an optional issue-type mapping per source, and an optional list of bot identities. Credentials with `${ENV_VAR}` references SHALL be resolved at load time so secrets never sit in the YAML.

#### Scenario: Config loaded with env-referenced credentials
- **WHEN** the config contains `github_token: ${GITHUB_TOKEN}` and the environment variable is set
- **THEN** the loaded config object exposes the resolved token value to providers

#### Scenario: Missing required env var fails loudly
- **WHEN** the config references `${GITHUB_TOKEN}` and the environment variable is not set
- **THEN** loading fails with an error naming the missing variable, before any HTTP server or scheduler starts

#### Scenario: Adding a project via configuration
- **WHEN** a new GitHub repository is added to the `projects.github` list and the process is restarted
- **THEN** on the next scheduler cycle, that repository is included in fetches without code changes

### Requirement: Scheduled in-process ingestion with per-provider concurrency control
The system SHALL run ingestion for all configured data sources via an in-process scheduler (APScheduler) on a configurable interval. Concurrent runs of the same provider SHALL be prevented by a per-provider in-memory mutex. If a scheduled tick fires while the previous run for that provider is still in flight, the new run SHALL be skipped (not queued) and logged.

#### Scenario: Incremental ingestion on schedule
- **WHEN** the scheduler triggers ingestion and a prior successful run exists for GitHub commits
- **THEN** the provider is called with `since` set to the `started_at` of the last successful run for `(github, commit)`, and only new commits are inserted into `raw_events`

#### Scenario: Overlapping run is skipped
- **WHEN** the GitHub provider is still mid-run and the next scheduled tick fires
- **THEN** the new run is skipped, an `ingestion_runs` row is written with `status = skipped`, and Jira ingestion is unaffected

#### Scenario: Per-provider error isolation
- **WHEN** the Jira provider consistently fails after all retries
- **THEN** the GitHub provider continues to ingest on schedule, and the Jira failure is logged with severity ERROR

### Requirement: Operator-triggered backfill via CLI
The system SHALL provide a `project-health backfill` command that performs a one-shot historical ingestion using the same provider and writer code as the scheduler, with `since = now - <window>`. The default window SHALL be `ingestion.backfill_days` (default 90); the CLI SHALL accept `--since` to override. Re-running the command SHALL be idempotent: existing `external_id` rows upsert.

#### Scenario: Initial backfill on first setup
- **WHEN** the operator runs `project-health backfill --since 90d` on a fresh database
- **THEN** all configured providers fetch events from the last 90 days and insert them into `raw_events`, with progress printed per provider

#### Scenario: Re-running backfill is safe
- **WHEN** the operator runs `project-health backfill --since 30d` and rows for those external IDs already exist
- **THEN** existing rows are upserted with the latest payload; no duplicates are created

### Requirement: Manual sync trigger via API
The system SHALL expose `POST /api/sync/run` that triggers an immediate ingestion run for one or more providers. The endpoint SHALL contend on the same per-provider mutex as the scheduler.

#### Scenario: Manual sync starts a run
- **WHEN** `POST /api/sync/run?source=github` is called and the GitHub provider is idle
- **THEN** the endpoint returns `202 Accepted` with the new `ingestion_runs.id` and a run starts asynchronously

#### Scenario: Manual sync rejected while busy
- **WHEN** `POST /api/sync/run?source=github` is called and a GitHub run is already in flight
- **THEN** the endpoint returns `409 Conflict` with the in-flight `ingestion_runs.id`

### Requirement: Ingestion observability
The system SHALL record every ingestion run in an `ingestion_runs` table with `id`, `source`, `event_type`, `started_at`, `finished_at`, `status` (running | success | failure | skipped), `trigger` (scheduled | manual | backfill), `events_count`, and `error_message`. The scheduler SHALL derive its `since` parameter from the most recent successful run for each `(source, event_type)`.

#### Scenario: Successful run recorded
- **WHEN** a scheduled GitHub commits run completes successfully and ingests 12 events
- **THEN** an `ingestion_runs` row exists with `status = success`, `events_count = 12`, `finished_at` set, and `trigger = scheduled`

#### Scenario: Failure recorded with message
- **WHEN** the Jira provider raises after exhausting retries
- **THEN** the corresponding `ingestion_runs` row has `status = failure`, `error_message` populated, and `finished_at` set

#### Scenario: Freshness exposed via API
- **WHEN** `GET /api/sync/status` is called
- **THEN** the response includes, per source, the timestamp of the most recent successful run and the status of the current run if any

### Requirement: Localhost-only HTTP binding (v1)
The system SHALL bind the FastAPI HTTP server to `127.0.0.1` only. Configuration SHALL reject any bind address that exposes the dashboard beyond localhost in v1.

#### Scenario: Server binds to localhost
- **WHEN** `project-health serve` starts
- **THEN** the HTTP server is reachable from `http://127.0.0.1:<port>` and NOT from other network interfaces

### Requirement: Raw event storage schema
The system SHALL store all ingested events in a `raw_events` table with fields `source`, `event_type`, `external_id`, `timestamp`, `ingested_at`, `actor`, `project`, and a JSONB `data` column for source-specific payload. Review events SHALL be stored as separate rows with `event_type = 'pull_request_review'`. A unique index on `(source, event_type, external_id)` SHALL enforce deduplication. Secondary indexes MUST exist on `(source, timestamp)`, `actor`, and `project`. Rows are append-only and never deleted; orphaned commits from force-pushes remain as historical truth.

#### Scenario: GitHub PR event stored with additions, deletions, and filtered LOC
- **WHEN** a GitHub pull request event is ingested
- **THEN** the `data` JSONB column contains `{ "additions": <int>, "deletions": <int>, "linguist_filtered_additions": <int>, "linguist_filtered_deletions": <int>, "state": "<open|closed>", "merged_at": <iso8601|null>, "reviewers": [...] }` and the event is queryable by `source = 'github'` and `event_type = 'pull_request'`

#### Scenario: GitHub review event stored with state and comment count
- **WHEN** a GitHub pull request review is ingested
- **THEN** the `data` JSONB column contains `{ "review_state": "<APPROVED|CHANGES_REQUESTED|COMMENTED>", "comment_count": <int>, "pr_external_id": "<pr-id>" }` and is queryable by `source = 'github'` and `event_type = 'pull_request_review'`

#### Scenario: Jira issue event stored with story points
- **WHEN** a Jira issue event is ingested
- **THEN** the `data` JSONB column contains `{ "issue_type": "<Bug|Story|Task|...>", "story_points": <float|null>, "status": "<string>", "labels": [...] }` and is queryable by `source = 'jira'` and `event_type = 'issue'`

#### Scenario: Deduplication on re-ingestion
- **WHEN** ingestion results contain an event with an `external_id` that already exists for the same `(source, event_type)`
- **THEN** the existing row is updated with the latest payload; no duplicate is inserted

### Requirement: Identity reconciliation from YAML
The system SHALL maintain `persons` and `person_identities` tables. On boot, the YAML `team` list SHALL be reconciled into these tables: each YAML team member becomes a `persons` row, and each declared source identity becomes a `person_identities` row linked to that person. Identities present in the database but no longer in YAML SHALL have their `person_id` retained (not deleted) for historical attribution.

#### Scenario: Boot-time reconciliation
- **WHEN** the YAML contains a team member with `github: jdoe` and `jira: 557058:abc-123`
- **THEN** after boot, `persons` contains a row for that member and `person_identities` contains two rows linked to it

### Requirement: Auto-discovery of unmapped identities
The system SHALL detect actors in ingested events that do not match any `person_identities` row, and SHALL insert a placeholder row with `person_id = NULL` so the operator can review and map them later. The CLI SHALL provide a `project-health identities list-unmapped` command that prints these placeholders.

#### Scenario: New actor in ingestion creates a placeholder
- **WHEN** a GitHub PR is ingested with author `octocat` and no `person_identities` row exists for `(github, octocat)`
- **THEN** a `person_identities` row is created with `person_id = NULL`, `source = github`, `external_id = octocat`

#### Scenario: Operator views unmapped identities
- **WHEN** the operator runs `project-health identities list-unmapped`
- **THEN** the command prints all `person_identities` rows where `person_id IS NULL`, grouped by source

### Requirement: Sprint storage
The system SHALL store Jira sprint definitions in a `sprints` table with `id`, `name`, `project`, `start_date`, `end_date`, and `state` fields, populated by the Jira provider's `fetch_sprints()` method.

#### Scenario: Sprint data refreshed on each ingestion cycle
- **WHEN** the Jira provider runs `fetch_sprints()`
- **THEN** all active and recently completed sprints (last 90 days) are upserted into the `sprints` table by `id`

### Requirement: Error handling and retry
The system SHALL handle provider errors gracefully. Transient failures (5xx, network errors) SHALL be retried with exponential backoff up to 3 attempts. Authentication failures (401, 403) SHALL fail fast without retry. All failures SHALL be logged and recorded in `ingestion_runs` without halting ingestion from other providers or event types.

#### Scenario: Transient API failure retries successfully
- **WHEN** a GitHub API call fails with a 503 status code
- **THEN** the provider retries up to 3 times with exponential backoff, and if any retry succeeds, ingestion completes normally

#### Scenario: Auth failure fails fast
- **WHEN** a GitHub API call returns 401 Unauthorized
- **THEN** the provider does not retry; the `ingestion_runs` row records `status = failure` with the auth error message

#### Scenario: Persistent failure does not block other providers
- **WHEN** the Jira provider consistently fails after all retries
- **THEN** the GitHub provider continues to ingest on schedule, and the Jira failure is logged with severity level ERROR
