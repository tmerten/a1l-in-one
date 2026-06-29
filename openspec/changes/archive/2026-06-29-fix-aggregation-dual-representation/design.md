## Context

The `add-launchpad-observation` change introduced a deliberate dual-representation model:

- Each code change is stored as both `pull_request` (legacy) and `change_request` (normalized) event types.
- Each review is stored as both `pull_request_review` (legacy) and `review_decision` (normalized) event types.

The storage layer correctly handles this via deduplication on `(source, event_type, external_id)` -- the same external_id can exist under different event types. However, the aggregation queries were written assuming these are independent event streams rather than dual views of the same underlying data.

Additionally, the Launchpad provider stores review-to-MP references using `change_request_external_id` while GitHub uses `pr_external_id`. Some queries handle this via COALESCE (collaboration), while others only check `pr_external_id` (velocity).

## Goals / Non-Goals

**Goals:**

- Eliminate double-counting of reviews across event types in all aggregation queries.
- Ensure Launchpad reviews are included in velocity/turnaround metrics via correct JOIN keys.
- Add Launchpad MPs to active work items.
- Fix `prs_merged` to only count PRs with `merged_at IS NOT NULL`.
- Fix review attribution in person detail contributions.
- Add missing source filtering in time-series queries.
- Handle absent line stats for LP MPs in size classification.

**Non-Goals:**

- Removing the dual-representation model (it exists for backward compatibility).
- Adding line-of-code stats for Launchpad (LP API doesn't expose this).
- Changing the provider or ingestion layers.
- Restructuring the `raw_events` table schema.

## Design Decision: Canonical Event Type for Reviews

### Problem

The scheduler fires jobs for both `pull_request_review` and `review_decision`. Both produce events with the same external_id but different event_type values. Aggregation queries that count both (`event_type IN ('pull_request_review', 'review_decision')`) double-count every review.

### Options

**Option A: Query only `review_decision` (the normalized type)**

All aggregation queries change to use `review_decision` as the canonical event type for counting reviews. The `pull_request_review` type is retained in storage for backward compatibility but ignored in metrics.

Pros:
- Simple single-type queries.
- `review_decision` is the normalized/abstract type, consistent with the abstraction design intent.
- Clear rule: aggregation always uses the normalized type.

Cons:
- GitHub's `review_decision` is a subset of `pull_request_review` (only reviews with a meaningful state like APPROVED/CHANGES_REQUESTED). "COMMENTED"-only reviews without a decision are excluded.

**Option B: Query only `pull_request_review` (the legacy type)**

All aggregation queries change to use `pull_request_review` as the canonical type. The `review_decision` type is retained for downstream consumers but not used in dashboards.

Pros:
- For GitHub, this captures ALL reviews including comment-only reviews.
- Backward compatible with existing data.

Cons:
- Less aligned with the abstraction direction.
- LP's `pull_request_review` is just a wrapper around `review_decision` (identical data).

**Option C: Query `review_decision` for decision counts, `review_comment` for comment counts**

Use `review_decision` when counting approvals/rejections, and `review_comment` when counting review commentary. Never query `pull_request_review` in aggregation.

Pros:
- Cleanest semantic separation.
- Each event type has a distinct meaning.
- Consistent across providers.

Cons:
- Requires confirming that all review comments (including GitHub review bodies) are stored as `review_comment` events (they are -- `fetch_review_comments` extracts them).
- Comment-only GitHub reviews without a state become invisible to decision counts (acceptable -- they're not decisions).

### Selected: Option C

Use `review_decision` for counting review decisions (approvals, rejections, change requests). Use `review_comment` for counting review commentary. Never reference `pull_request_review` in aggregation queries. This gives the cleanest semantics and avoids all double-counting.

## Design Decision: Review-to-PR JOIN Key

### Problem

GitHub stores `pr_external_id` in review data. Launchpad stores `change_request_external_id`. The velocity query only checks `pr_external_id`, missing all LP reviews.

### Solution

Use `COALESCE(json_extract(r.data, '$.pr_external_id'), json_extract(r.data, '$.change_request_external_id'))` in all JOINs that link reviews to their parent change request. This pattern is already used correctly in the collaboration query and should be applied consistently.

Additionally, ensure `r.source = pr.source` in JOINs to prevent accidental cross-source matching (e.g., a GitHub review with `pr_external_id = "42"` matching a LP merge proposal that happens to have external_id "42").

## Design Decision: PR Merged Count

### Problem

`_person_metrics` uses `COUNT(*)` which includes ALL `pull_request` events (open, closed, merged) and assigns the total to both `prs_opened` and `prs_merged`.

### Solution

Add a separate SQL column:
```sql
COALESCE(SUM(CASE WHEN event_type = 'pull_request' AND json_extract(data, '$.merged_at') IS NOT NULL THEN 1 END), 0) as prs_merged
```

Keep `cnt` for `prs_opened` (all PRs authored by this person).

## Design Decision: Active Work Items for LP MPs

### Problem

The active filter has conditions for GitHub PRs, GitHub issues, Jira issues, and LP issues, but no condition for LP merge proposals.

### Solution

Add:
```sql
OR (source = 'launchpad' AND event_type = 'pull_request' AND json_extract(data, '$.state') = 'open')
```

LP's `normalize_launchpad_mp_state()` maps "Work in progress", "Needs review", and "Approved" to `"open"`, so this correctly identifies active MPs.

## Design Decision: LP MPs in PR Size Classification

### Problem

LP MPs don't have `linguist_filtered_additions`/`linguist_filtered_deletions`. They default to 0, making all LP MPs "small".

### Solution

Exclude LP MPs from PR size classification entirely. The composition metric should only classify PRs where line stats are available. Add a `source != 'launchpad'` filter or check that at least one of the stat fields is non-null before classifying.

Report LP MP count separately in the composition response as `unclassified_mps` or similar for transparency.

## Design Decision: Person Detail Reviews

### Problem

`_person_detail_contributions` at line 667 uses `=` assignment for reviews, so the last event_type row processed overwrites previous ones.

### Solution

Split review-related metrics into distinct counters:
- `review_decisions` counted from `review_decision` events only
- `review_comments` counted from `review_comment` events only

Map these to the response as `reviews_given` (decisions) and `review_comments` (comments). Do not combine heterogeneous event types in a single assignment.

## Design Decision: Time-Series Source Filtering

### Problem

`contribution_volume_ts` does not call `_source_filter()`, unlike its non-ts counterpart.

### Solution

Apply the same `_source_filter()` calls that are used in `contribution_volume()`. Filter commits to commit-capable sources, PRs to pull_request-capable sources, and issues to issue-capable sources.

## Changes Summary

| File | Change |
|------|--------|
| `aggregation/queries.py` | Fix all 8 bugs in the query layer |
| `tests/test_unified_contributions.py` | Add tests with dual-representation events |
| `tests/test_work_items.py` | Add test for active LP MPs |

No migrations, no provider changes, no frontend changes needed.
