## Why

The `add-launchpad-observation` change introduced a dual-representation strategy where GitHub PRs and Launchpad Merge Proposals are stored as both legacy `pull_request` events and provider-neutral `change_request` events. Similarly, reviews are stored as both `pull_request_review` and `review_decision` events. The ingestion and storage layers handle this correctly, but the aggregation queries were not updated to account for the same conceptual event existing under multiple event types.

This causes:

- Review counts doubled in person metrics and per-source breakdowns (both `pull_request_review` and `review_decision` rows counted).
- Velocity review turnaround metrics invisible for Launchpad (JOIN uses `pr_external_id` but LP stores `change_request_external_id`).
- Active work items never showing open Launchpad merge proposals.
- `prs_merged` incorrectly equaling total PR count (including unmerged).
- Per-person review attribution inconsistent due to assignment overwrite logic.
- All Launchpad MPs classified as "small" in composition metrics (no line stats available).

The tests pass because they write only one event type at a time rather than simulating the full ingestion pipeline that produces both representations simultaneously.

## What Changes

- Fix aggregation queries to avoid double-counting events that exist under both legacy and normalized event types.
- Fix the velocity review turnaround JOIN to use COALESCE for the change request reference key (matching the pattern already used in the collaboration query).
- Add Launchpad merge proposals to the active work items filter.
- Fix `prs_merged` computation to count only PRs with `merged_at IS NOT NULL`.
- Fix `_person_detail_contributions` to properly accumulate review counts instead of overwriting.
- Add source filtering to `contribution_volume_ts`.
- Handle missing line stats gracefully for LP MPs in composition metrics.

## Impact

- **Aggregation layer**: All queries in `aggregation/queries.py` that reference `pull_request_review` or `review_decision` need to pick one canonical type or deduplicate.
- **Tests**: Need new tests that write BOTH `pull_request_review` AND `review_decision` events to verify no double-counting.
- **API responses**: Metric values will change (decrease) for anyone with Launchpad data due to removal of double-counting.
- **No schema changes**: All fixes are in query logic, no migrations needed.

## Non-Goals

- Removing the dual-representation storage model. The `pull_request` / `change_request` and `pull_request_review` / `review_decision` duality is intentional for backward compatibility.
- Adding line-of-code stats for Launchpad MPs (LP API does not expose this).
- Changing the ingestion or provider layers.
