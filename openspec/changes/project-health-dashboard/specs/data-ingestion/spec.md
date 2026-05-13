## ADDED Requirements

### Requirement: Extensible data source provider interface
The system SHALL define a `DataSourceProvider` interface that each data source (GitHub, Jira, future Launchpad) implements. Each provider MUST support a health check and return typed event arrays for the event types it supports, including PR reviews as a first-class event type.

#### Scenario: Provider returns events for a supported type
- **WHEN** the GitHub provider is invoked with `fetchPullRequests(since)` for a valid repository
- **THEN** it returns an array of `RawPREvent` objects, each with `external_id`, `timestamp`, `actor`, `project`, and source-specific data

#### Scenario: Provider returns review events
- **WHEN** the GitHub provider is invoked with `fetchPullRequestReviews(since)` for a valid repository
- **THEN** it returns an array of `RawReviewEvent` objects, each with `external_id` (the review ID), `timestamp`, `actor` (the reviewer), `project`, and a data payload containing `state` (APPROVED | CHANGES_REQUESTED | COMMENTED) and `comment_count`

#### Scenario: Provider returns empty for unsupported event type
- **WHEN** the GitHub provider is invoked with `fetchSprints()`
- **THEN** it returns an empty array

#### Scenario: Provider health check fails
- **WHEN** a provider's credentials are invalid or the upstream API is unreachable
- **THEN** `healthCheck()` returns `false` and the scheduler logs the failure without halting other providers

### Requirement: Scheduled data ingestion
The system SHALL run ingestion for all configured data sources on a configurable schedule, with each run fetching only events newer than the most recent stored event for that source and event type.

#### Scenario: Incremental ingestion on schedule
- **WHEN** the scheduler triggers ingestion and a prior run exists for GitHub commits
- **THEN** the provider is called with `since` set to the timestamp of the last ingested commit, and only new commits are inserted into `raw_events`

#### Scenario: First-time ingestion (backfill)
- **WHEN** a data source is configured for the first time with no prior events in `raw_events`
- **THEN** the provider fetches events from a configurable lookback window (default 90 days) and inserts all of them

#### Scenario: Ingestion deduplication
- **WHEN** ingestion results contain an event with an `external_id` that already exists for the same source and event type
- **THEN** the existing row is updated with the latest data, and no duplicate is inserted

### Requirement: Raw event storage schema
The system SHALL store all ingested events in a `raw_events` table with fields `source`, `event_type`, `external_id`, `timestamp`, `ingested_at`, `actor`, `project`, and a JSONB `data` column for source-specific payload. Review events SHALL be stored as separate rows with `event_type = 'pull_request_review'`, capturing review state and inline comment count in the `data` payload. Indexes MUST exist on `(source, timestamp)`, `actor`, and `project`.

#### Scenario: GitHub PR event stored with additions and deletions
- **WHEN** a GitHub pull request event is ingested
- **THEN** the `data` JSONB column contains `{ "additions": <int>, "deletions": <int>, "state": "<open|closed|merged>", "reviewers": [...] }` and the event is queryable by `source = 'github'` and `event_type = 'pull_request'`

#### Scenario: GitHub review event stored with state and comment count
- **WHEN** a GitHub pull request review is ingested
- **THEN** the `data` JSONB column contains `{ "review_state": "<APPROVED|CHANGES_REQUESTED|COMMENTED>", "comment_count": <int>, "pr_external_id": "<pr-id>" }` and the event is queryable by `source = 'github'` and `event_type = 'pull_request_review'`

#### Scenario: Jira issue event stored with story points
- **WHEN** a Jira issue event is ingested
- **THEN** the `data` JSONB column contains `{ "issue_type": "<Bug|Feature|Task|...>", "story_points": <float>, "status": "<string>", "labels": [...] }` and the event is queryable by `source = 'jira'` and `event_type = 'issue'`

### Requirement: Sprint storage
The system SHALL store Jira sprint definitions in a `sprints` table with `id`, `name`, `project`, `start_date`, `end_date`, and `state` fields, populated by the Jira provider's `fetchSprints()` method.

#### Scenario: Sprint data refreshed on each ingestion cycle
- **WHEN** the Jira provider runs `fetchSprints()`
- **THEN** all active and recently completed sprints (last 90 days) are upserted into the `sprints` table by `id`

### Requirement: Provider configuration
The system SHALL support per-provider configuration (API credentials, repository/project keys, event type filters) via a configuration store, and MUST allow providers to be added without code changes to the ingestion scheduler.

#### Scenario: Adding a new provider via configuration
- **WHEN** a new provider entry is added to the configuration with type "github", credentials, and repository list
- **THEN** on the next scheduler cycle, the provider is instantiated and begins ingesting data

### Requirement: Error handling and retry
The system SHALL handle provider errors gracefully, retry on transient failures with exponential backoff, and log all failures without halting ingestion from other providers or event types.

#### Scenario: Transient API failure retries successfully
- **WHEN** a GitHub API call fails with a 503 status code
- **THEN** the provider retries up to 3 times with exponential backoff, and if any retry succeeds, ingestion completes normally

#### Scenario: Persistent failure does not block other providers
- **WHEN** the Jira provider consistently fails after all retries
- **THEN** the GitHub provider continues to ingest on schedule, and the Jira failure is logged with severity level ERROR
