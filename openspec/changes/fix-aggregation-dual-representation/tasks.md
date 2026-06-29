## 1. Fix Review Double-Counting

- [x] 1.1 In `_person_metrics`, replace `event_type IN ('pull_request_review', 'review_decision')` with `event_type = 'review_decision'` for the `reviews_given` counter.
- [x] 1.2 In `_contribution_volume_per_source`, change `COUNT(CASE WHEN event_type IN ('pull_request_review', 'review_decision') THEN 1 END)` to count only `review_decision`.
- [x] 1.3 In `collaboration` query, change `r.event_type IN ('pull_request_review', 'review_decision')` to `r.event_type = 'review_decision'`.
- [x] 1.4 In `_person_metrics` review SQL (line 788), change `event_type IN ('pull_request_review', 'review_decision', 'review_comment')` to `event_type IN ('review_decision', 'review_comment')`.
- [x] 1.5 In `collaboration_ts`, change `event_type = 'pull_request_review'` to `event_type = 'review_decision'` and update the `_source_filter` call accordingly.

## 2. Fix Velocity Review Turnaround JOIN

- [x] 2.1 In the velocity `review_sql` JOIN condition, change `json_extract(r.data, '$.pr_external_id') = pr.external_id` to `COALESCE(json_extract(r.data, '$.pr_external_id'), json_extract(r.data, '$.change_request_external_id')) = pr.external_id`.
- [x] 2.2 Change the review event type filter from `r.event_type = 'pull_request_review'` to `r.event_type = 'review_decision'` in the velocity query.
- [x] 2.3 Add `r.source = pr.source` to the velocity JOIN condition to prevent cross-source matching.
- [x] 2.4 Update the `_source_filter` call from `"review_decision"` alias to match the actual event type queried.

## 3. Fix `prs_merged` Computation

- [x] 3.1 In `_person_metrics`, add a `prs_merged` column to the SQL: `COALESCE(SUM(CASE WHEN event_type = 'pull_request' AND json_extract(data, '$.merged_at') IS NOT NULL THEN 1 END), 0) as prs_merged`.
- [x] 3.2 Update the Python code to use `row["prs_merged"]` for `metrics["prs_merged"]` instead of `row["cnt"]`.
- [x] 3.3 Keep `row["cnt"]` for `metrics["prs_opened"]` (total PR count authored).

## 4. Fix Active Work Items for LP MPs

- [x] 4.1 Add `OR (source = 'launchpad' AND event_type = 'pull_request' AND json_extract(data, '$.state') = 'open')` to the active work items filter in the `work_items` method.

## 5. Fix Person Detail Contributions Review Assignment

- [x] 5.1 In `_person_detail_contributions`, split the review handling: use `review_decision` count for `reviews_given` and `review_comment` count for a separate `review_comments` field.
- [x] 5.2 Remove `pull_request_review` from the condition entirely.
- [x] 5.3 Ensure that when both `review_decision` and `review_comment` rows exist, they populate different fields rather than overwriting each other.

## 6. Fix PR Size Classification for LP MPs

- [x] 6.1 In the `composition` query, add a condition to exclude PRs where both `linguist_filtered_additions` and `linguist_filtered_deletions` are null or zero AND `source = 'launchpad'`, or filter to only classify PRs from sources that provide line stats.
- [x] 6.2 Alternatively, skip size classification when no line stats are available and report these as unclassified.

## 7. Add Source Filtering to Time-Series Queries

- [x] 7.1 In `contribution_volume_ts`, apply `_source_filter("commit")`, `_source_filter("pull_request")`, and `_source_filter("issue")` to restrict event counts to capable sources.
- [x] 7.2 Update the SQL to use the source filter clauses within the CASE WHEN expressions or as additional WHERE conditions.

## 8. Add Tests for Dual-Representation Scenarios

- [x] 8.1 Add a test that writes BOTH `pull_request_review` AND `review_decision` events with the same external_id and asserts `reviews_given` is NOT doubled.
- [x] 8.2 Add a test for velocity review turnaround with LP review events using `change_request_external_id` and assert the turnaround is computed.
- [x] 8.3 Add a test for active work items that includes an open LP merge proposal and asserts it appears in results.
- [x] 8.4 Add a test that writes both merged and unmerged PRs and asserts `prs_merged < prs_opened`.
- [x] 8.5 Add a test for `_person_detail_contributions` with both `review_decision` and `review_comment` events and assert both fields are populated independently.
- [x] 8.6 Add a test for `contribution_volume_per_source` with dual-representation events and assert no double-counting.

## 9. Verification

- [x] 9.1 Run backend linting (`ruff check`).
- [x] 9.2 Run type checks (`mypy`).
- [x] 9.3 Run full test suite and confirm all 84+ tests pass.
- [x] 9.4 Verify no regressions in existing test assertions (metric values may decrease due to removed double-counting).
