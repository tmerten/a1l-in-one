## 1. Launchpad Configuration

- [x] 1.1 Add `LaunchpadConfig`, `LaunchpadBugTargetConfig`, and `LaunchpadRepositoryConfig` models to the app config schema.
- [x] 1.2 Support separate `launchpad-bugs` and `launchpad-repos` config lists with no association between bug targets and repositories.
- [x] 1.3 Parse canonical Launchpad repo paths such as `~maas-committers/maas/+git/maas-release-tools` into owner, context, and repository fields.
- [x] 1.4 Add optional Launchpad credentials to the config loader without reading token environment variables outside the loader.
- [x] 1.5 Update `project-health.example.yaml` with commented Launchpad examples for separate bug targets and repository targets.

## 2. Datasource And Target Metadata

- [x] 2.1 Extend datasource metadata to represent Launchpad bug targets and repositories as separate target types.
- [x] 2.2 Update `GET /api/projects` or its datasource payload to expose Launchpad bug targets and repositories separately.
- [x] 2.3 Keep existing consumers compatible by preserving current project arrays or adding an additive grouped field.
- [x] 2.4 Update frontend API types after backend schema changes.

## 3. Change Request Abstraction

- [x] 3.1 Add provider-neutral `change_request`, `review_request`, `review_decision`, and `review_comment` event normalization.
- [x] 3.2 Define source capability flags for review comments, inline comments, review requests, review decisions, and approval state.
- [x] 3.3 Map GitHub PR events into `change_request` without removing existing GitHub-specific fields.
- [x] 3.4 Map GitHub requested reviewers, reviews, review bodies, and review comments into the provider-neutral review concepts.
- [x] 3.5 Map Launchpad merge proposals, vote references, and code review comments into the provider-neutral change request and review concepts.
- [x] 3.6 Preserve source-specific review/comment kind in raw payloads and normalized metadata.
- [x] 3.7 Update aggregation naming so cross-source totals use `change_requests` while source drill-downs use `Pull Requests` and `Merge Proposals`.
- [x] 3.8 Decide during implementation whether to add a small `normalized_interactions` table now or defer it while preserving all graph-ready atoms in raw events.

## 4. Launchpad Client And Provider

- [x] 4.1 Implement `LaunchpadClient` with read-only GET/HEAD-only HTTP behavior.
- [x] 4.2 Add client methods for bug targets, repository metadata, commits, merge proposals, code review comments, vote references, people, and teams as supported by Launchpad API responses.
- [x] 4.3 Implement `LaunchpadProvider` that enumerates configured bug targets and repository targets.
- [x] 4.4 Normalize configured Launchpad bug tasks into `issue` / work-item events with parent bug payload preserved in raw data.
- [x] 4.5 Map Launchpad bug task fields: target, title, description, status, normalized status, importance/priority, assignee, reporter, milestone, tags, timestamps, and URL.
- [x] 4.6 Treat `Fix Committed` and `Fix Released` as completed contribution states; preserve non-fix terminal states without counting them as fixed work.
- [x] 4.7 Normalize Launchpad commits into `commit` events with repository target metadata and author identity.
- [x] 4.8 Normalize Launchpad merge proposals into `change_request` events with MP state, author, branches, target repository, timestamps, and capability flags.
- [x] 4.9 Normalize Launchpad vote references into `review_request` / reviewer-state events.
- [x] 4.10 Normalize Launchpad vote-bearing comments into `review_decision` events using the agreed vote mapping.
- [x] 4.11 Normalize Launchpad code review comments into `review_comment` events.
- [x] 4.12 Track sync health independently for bug targets and repository targets.

## 5. Identity Resolution

- [x] 5.1 Add Launchpad identities to `person_identities` using stable Launchpad person/team identifiers from API responses.
- [x] 5.2 Include Launchpad display names and profile URLs in identity detail responses where available.
- [x] 5.3 Ensure person-centric queries include Launchpad actors across bugs, commits, and MPs.
- [x] 5.4 Ensure bot/service-account filters apply to Launchpad identities where configured.

## 6. Aggregation And Metrics

- [x] 6.1 Include Launchpad bug task events in issue/work-item metrics for reported, assigned, completed, and status breakdowns.
- [x] 6.2 Count Launchpad `Fix Committed` and `Fix Released` as resolved/completed contribution; do not count `Invalid`, `Won't Fix`, `Expired`, `Opinion`, or `Does Not Exist` as fixed work.
- [x] 6.3 Include Launchpad commits in contribution volume and per-repository person metrics.
- [x] 6.4 Include GitHub PRs and Launchpad MPs in change request counts and cycle-time metrics when timestamps are available.
- [x] 6.5 Include GitHub reviews and Launchpad votes in normalized review decision metrics.
- [x] 6.6 Include GitHub review comments and Launchpad code review comments in comparable review comment metrics while preserving source-specific comment type.
- [x] 6.7 Exclude Launchpad MPs from GitHub-only unresolved-thread metrics unless an equivalent Launchpad concept is verified.
- [x] 6.8 Add datasource and target filters for Launchpad bug targets and repository targets.
- [x] 6.9 Update cache keys and invalidation paths for Launchpad datasource, bug targets, and repository targets.

## 7. Frontend

- [x] 7.1 Update datasource/project filter UI to show Launchpad bug targets and repositories as separate target types.
- [x] 7.2 Add Launchpad sync status display with separate bug-target and repository-target health where available.
- [x] 7.3 Add Launchpad sections to person drill-down: Bugs, Commits, and Merge Proposals.
- [x] 7.4 Use `Change Requests` for cross-source aggregate cards and source-specific labels in drill-downs.
- [x] 7.5 Avoid rendering unavailable GitHub-only fields such as unresolved review threads for Launchpad MPs; show source capability messaging when needed.

## 8. Tests

- [x] 8.1 Test Launchpad config parsing for separate bug target and repository lists.
- [x] 8.2 Test canonical Launchpad repository path parsing and duplicate repository validation.
- [x] 8.3 Test datasource payload includes Launchpad bug targets and repositories without false project ownership.
- [x] 8.4 Test Launchpad client read-only guard rejects non-GET/HEAD methods.
- [x] 8.5 Add recorded HTTP cassettes for Launchpad bugs, repositories, commits, merge proposals, code review comments, vote references, people, and teams.
- [x] 8.6 Use the public repo `~maas-committers/maas/+git/maas-release-tools` for Launchpad repository API verification where suitable.
- [x] 8.7 Test Launchpad ingestion with a real SQLite database and assert stored raw events and normalized observable outputs.
- [x] 8.8 Test person aggregation includes Launchpad bugs, commits, MPs, review decisions, and review comments for a resolved person identity.
- [x] 8.9 Test GitHub PRs and reviews also populate provider-neutral change request/review concepts.
- [x] 8.10 Test Launchpad MPs contribute to change request and review decision counts but not GitHub-only unresolved-thread metrics.
- [x] 8.11 Test frontend rendering for Launchpad bug targets, repositories, and MP review/comment detail.

## 9. Jira / Launchpad Bug Mapping Validation

- [x] 9.1 Test Launchpad bug task status mapping, including `Fix Committed` and `Fix Released` as completed contribution states.
- [x] 9.2 Test non-fix terminal statuses are preserved but do not count as fixed/resolved contribution.
- [x] 9.3 Test assignee receives completed work credit when present and reporter remains available for reported/opened work.

## 10. Verification

- [x] 10.1 Run backend linting and type checks.
- [x] 10.2 Run backend tests.
- [x] 10.3 Regenerate frontend API types if OpenAPI changed.
- [x] 10.4 Run frontend type checks and build.
- [ ] 10.5 Manually verify a configured Launchpad datasource appears in filters, sync status, person drill-downs, and aggregate metrics.
