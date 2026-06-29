## Context

The dashboard already treats GitHub and Jira as datasources and is moving toward person-centric aggregation across sources. Launchpad should join that model, but Launchpad has different domain boundaries than GitHub:

- Bugs are attached to Launchpad projects or distributions and should be treated similarly to Jira work items.
- Code repositories can be owned by a person or team and should be treated similarly to GitHub repositories.
- Merge proposals represent proposed code changes, but their public API shape differs from GitHub pull requests, especially around review comments, requested changes, and resolution detail.

The implementation should model Launchpad accurately rather than hiding these differences behind GitHub terminology.

## Goals / Non-Goals

**Goals:**

- Add read-only Launchpad ingestion for bugs, repositories, commits, merge proposals, reviews, comments, people, and teams.
- Support Launchpad bug targets and repository targets as separate config lists, with no project/repository association.
- Include Launchpad activity in person-centric contribution views and datasource/project filters.
- Represent both GitHub pull requests and Launchpad merge proposals as change requests with provider-neutral review concepts.
- Preserve Launchpad-specific data needed for drill-down and future metric improvements.

**Non-Goals:**

- No provider write operations.
- No attempt to synthesize review-thread resolution or inline-comment semantics that are not available from a provider.
- No automatic repository-to-project inference unless Launchpad explicitly exposes a relationship in the observed API response.
- No deep cross-provider linking between Jira issues, Launchpad bugs, GitHub PRs, and Launchpad MPs beyond references that are explicitly present in ingested data.

## Configuration Options

### Option 1: Fully Decoupled Lists

```yaml
launchpad_bugs:
  projects:
    - ubuntu
    - cloud-init

launchpad_repos:
  repositories:
    - owner: ~ubuntu-server
      name: ubuntu-server
    - owner: ~canonical-foundations
      name: curtin
```

**Pros:**

- Matches Launchpad's reality that bugs and repositories have different ownership models.
- Simple ingestion configuration: bug sync reads project targets; repo sync reads repository targets.
- Avoids misleading project/repo relationships.

**Cons:**

- Weak UI grouping. Users may not understand which repositories are operationally related to which bug projects.
- Harder to answer project-level questions that combine bugs and code work.
- Repeats settings such as sync cadence and display grouping if the same team wants both bugs and repos observed together.

### Option 2: Strict Project-First Hierarchy

```yaml
launchpad:
  projects:
    - name: ubuntu
      bugs: true
      repositories:
        - owner: ~ubuntu-server
          name: ubuntu-server
```

**Pros:**

- Easy to understand in the dashboard: one Launchpad project contains bug and code activity.
- Natural fit for project-level reporting and filters.
- Keeps related configuration in one place.

**Cons:**

- Can encode false relationships. A repository owned by a team or person may not belong to the configured project.
- Fails for standalone repositories or shared team repositories that support multiple projects.
- Forces users to invent artificial project ownership when they only want repository observation.

### Option 3: Hybrid Project Groups Plus Standalone Repositories

```yaml
launchpad:
  projects:
    - name: ubuntu
      display_name: Ubuntu
      bugs:
        enabled: true
      repositories:
        - owner: ~ubuntu-server
          name: ubuntu-server
        - owner: ~canonical-foundations
          name: curtin
  repositories:
    - owner: ~example-team
      name: standalone-tool
      group: tooling
```

**Pros:**

- Keeps project-scoped bugs and intentionally associated repositories together for reporting.
- Allows repositories that do not have a clean Launchpad project association.
- Makes the relationship explicit: repositories under a project are user-declared reporting associations, not inferred Launchpad ownership.
- Supports dashboard grouping without sacrificing Launchpad's domain model.

**Cons:**

- Slightly more complex config schema.
- Requires clear labels in the UI so users understand a project group may be a dashboard grouping, not a Launchpad-owned repository relationship.
- The same repository could be configured twice unless validation rejects duplicates.

### Decision

Use Option 1: fully decoupled lists.

Launchpad bugs and repositories are different observation targets and should not be connected in ingestion configuration. Bugs are comparable to Jira work items. Repositories are comparable to GitHub repositories. If the dashboard later needs a reporting bundle that says “show MAAS bugs plus these MAAS-related repositories,” that should be a dashboard grouping feature, not a Launchpad source-model assumption.

## Proposed Configuration Schema

```yaml
launchpad-bugs:
  - maas

launchpad-repos:
  - ~maas-committers/maas-ci/+git/maas-ci-internal
  - ~maas-committers/maas-images/+git/maas-v3-streams-candidate-signed
  - ~maas-committers/maas/+git/maas-release-tools
```

Validation rules:

- `launchpad-bugs` entries are Launchpad bug target names, such as project names.
- `launchpad-repos` entries are canonical Launchpad Git repository paths, e.g. `~team/project/+git/repository`.
- Duplicate repository targets are rejected after canonicalization.
- Empty Launchpad config is allowed but produces an unconfigured datasource.
- Credentials are loaded only through the app config loader.

## Domain Model

### Launchpad Targets

Introduce normalized config models:

```python
class LaunchpadBugTarget(BaseModel):
    name: str
    display_name: str | None = None
    statuses: list[str] | None = None

class LaunchpadRepositoryTarget(BaseModel):
    path: str                        # "~team/project/+git/repo"
    owner: str                       # parsed from path
    project_or_context: str          # parsed from path
    repository: str                  # parsed from path
    display_name: str | None = None
```

No field links a repository target to a bug target. Any such relationship would be user/reporting metadata outside Launchpad ingestion.

### Raw Events

Store source payloads in `raw_events` and produce provider-neutral event types for both GitHub and Launchpad:

- `issue` for Launchpad bugs and Jira/GitHub issues.
- `commit` for repository commits.
- `change_request` for GitHub pull requests and Launchpad merge proposals.
- `review_request` for requested/pending reviewers.
- `review_decision` for approvals, changes requested, disapprovals, and similar source-native decisions.
- `review_comment` for human review discussion comments.

The raw payload should preserve the Launchpad API response for future fields. Normalized columns should include source, project/group, actor, timestamp, event type, external ID, title, URL, state, and target repository where applicable.

## Provider-Neutral Review Model

The people views are the most important part of this project, so contribution concepts must be comparable across GitHub, Launchpad, and future platforms. GitHub PRs and Launchpad MPs should both map into shared concepts while preserving source-native details in `data`.

```text
change_request
├── review_request
├── review_decision
├── review_comment
└── lifecycle/status updates
```

### GitHub Mapping

- Pull request -> `change_request`.
- Requested reviewers -> `review_request`.
- Pull request review -> `review_decision` when it has a meaningful state such as `APPROVED`, `CHANGES_REQUESTED`, or `COMMENTED`.
- Pull request review body and review comments -> `review_comment` where available.
- Inline review comments should preserve `is_inline = true` or equivalent source metadata.

### Launchpad Mapping

- Branch merge proposal -> `change_request`.
- `votes_collection_link` / pending vote references -> `review_request` or current reviewer state.
- `code_review_comment.vote` -> `review_decision` when present.
- `code_review_comment.content` -> `review_comment`.
- `queue_status`, `date_review_requested`, `date_reviewed`, and `date_merged` -> lifecycle/status fields on the change request.

### Review Decision Mapping

Launchpad source votes map to normalized states as follows:

| Launchpad vote | Normalized state |
|---|---|
| `Approve` | `approved` |
| `Needs Fixing` | `changes_requested` |
| `Needs Resubmitting` | `changes_requested` |
| `Needs Information` | `needs_information` |
| `Disapprove` | `rejected` |
| `Abstain` | `neutral` |

GitHub review states map similarly:

| GitHub state | Normalized state |
|---|---|
| `APPROVED` | `approved` |
| `CHANGES_REQUESTED` | `changes_requested` |
| `COMMENTED` | `commented` |
| `DISMISSED` | `dismissed` |

Review comments from both providers map to the same `review_comment` concept for comparable people contributions. Source-specific metadata must distinguish inline comments, top-level discussion comments, review bodies, vote-bearing Launchpad comments, and deleted/edited comments where available.

## Collaboration Graph Readiness

This feature does not need to implement a full review/collaboration graph, but the database should preserve graph-ready atoms:

- actor identity: who performed the interaction.
- target identity: who received or authored the reviewed work when known.
- subject: change request, issue, bug, commit, or repository.
- interaction type: review requested, decision given, comment made, change merged.
- normalized state and source-native state.
- timestamp.
- source and source-native IDs.

If a normalized table is introduced now, keep it small and append/upsert-oriented:

```text
normalized_interactions
├── id
├── source
├── raw_event_id
├── interaction_type
├── subject_type
├── subject_external_id
├── from_identity_id
├── to_identity_id
├── project
├── repository
├── timestamp
├── normalized_state
└── data
```

If the normalized table is deferred, the raw events and normalized event vocabulary must still retain all fields needed to build it later without re-fetching historical provider data.

## Launchpad Bug Mapping

Launchpad bugs should be treated as Jira-like work items, but the primary normalized unit is the configured target's `bug_task`, not only the root `bug`. A single Launchpad bug can have multiple tasks against different products, distributions, or packages. The provider should ingest bug tasks for configured `launchpad-bugs` targets and preserve the parent bug payload as source detail.

```text
Launchpad bug
├── parent metadata: title, description, reporter, tags, duplicate info, messages
└── bug tasks
    ├── maas          -> ingest when `maas` is configured
    ├── ubuntu        -> ignore unless `ubuntu` is configured
    └── package/foo   -> ignore unless that target is configured
```

### Work Item Field Mapping

| Common field | Jira issue | Launchpad bug task |
|---|---|---|
| `external_id` | issue key | canonical task ID or `<target>:<bug_id>` |
| `work_item_id` | issue key | bug ID |
| `title` | summary | bug task title / bug title |
| `description` | description | bug description |
| `project` / `target` | Jira project key | bug target name |
| `issue_type` | Jira issue type | `bug` |
| `status` | Jira status name | bug task status |
| `normalized_status` | derived from status | derived from bug task status |
| `priority` | Jira priority if fetched later | Launchpad importance |
| `assignee` | assignee account ID | assignee link / person ID |
| `reporter` | reporter account ID | bug owner link / person ID |
| `created_at` | created | bug task date created or bug date created |
| `updated_at` | updated | bug date last updated |
| `resolutiondate` | resolution date | `date_fix_committed` or `date_fix_released` |
| `closed_at` | resolution date | `date_closed` |
| `labels` | labels | tags |
| `milestone` | fix version/sprint if fetched later | milestone link |
| `story_points` | story point custom field | null |
| `url` | browser/self URL | bug task web link |

### Status Mapping

Launchpad status maps to normalized work-item status as follows:

| Launchpad status | Normalized status | Contribution completed? |
|---|---|---|
| `New` | `open` | no |
| `Confirmed` | `open` | no |
| `Triaged` | `ready` | no |
| `Incomplete` | `needs_information` | no |
| `In Progress` | `in_progress` | no |
| `Fix Committed` | `done` | yes |
| `Fix Released` | `done` | yes |
| `Invalid` | `cancelled` | no |
| `Won't Fix` | `cancelled` | no |
| `Expired` | `cancelled` | no |
| `Opinion` | `non_actionable` | no |
| `Deferred` | `deferred` | no |
| `Does Not Exist` | `cancelled` | no |
| `Unknown` | `unknown` | no |

For people metrics, `Fix Committed` is the completion point. `Fix Released` does not add additional contribution credit because release work is tracked separately by other work items. Closed non-fix statuses are terminal lifecycle states but should not count as fixed/resolved contribution unless a future metric explicitly measures triage/closure work.

### Actor Semantics

The raw event should preserve role-specific identities instead of relying only on a single `actor` field:

- `reporter`: root bug owner.
- `assignee`: bug task assignee.
- `actor`: assignee if present, otherwise reporter, for compatibility with existing person queries.
- Future activity-derived actors: commenter, triager, status changer, closer, or fixer if Launchpad activity events are ingested later.

For v1 people metrics, assigned/completed work credit should flow to the assignee when present. Reporter credit should remain visible as reported/opened work but should not be treated as implementation completion.

## Merge Proposal Mapping

Launchpad MPs should not be forced into the GitHub PR model. Use a provider-neutral `change_request` abstraction with source capability flags.

### Shared Change Request Fields

These fields are available or reasonably derivable for both GitHub PRs and Launchpad MPs:

- `source`: `github` or `launchpad`.
- `external_id`.
- `title`.
- `url`.
- `author`.
- `target_repository`.
- `source_branch`.
- `target_branch`.
- `created_at`.
- `updated_at`.
- `closed_at` where available.
- `merged_at` or equivalent landed timestamp where available.
- `state`: provider-normalized `open`, `closed`, `merged`, `superseded`, `unknown`.
- `lines_added` / `lines_removed` when the provider exposes diff stats or when they can be computed safely from fetched diffs.

### Capability Differences

GitHub PRs and Launchpad MPs both expose review and comment concepts, but the source semantics are different. GitHub has review objects and inline review comments. Launchpad has code review comments and vote references. The shared model should maximize comparable people metrics while preserving source-specific comment type and decision detail.

Represent this explicitly:

```json
{
  "source": "launchpad",
  "kind": "merge_proposal",
  "capabilities": {
    "review_comments": true,
    "review_decisions": true,
    "line_comments": "unknown",
    "approval_state": "source_specific",
    "review_requests": true
  }
}
```

### Metric Mapping

- Count GitHub PRs and Launchpad MPs as `change_requests_opened`, `change_requests_closed`, and `change_requests_merged` where state supports it.
- Include MPs in person contribution volume and cycle-time metrics when timestamps exist.
- Count GitHub reviews and Launchpad votes as `review_decisions` using normalized states.
- Count GitHub review comments and Launchpad code review comments as `review_comments`, while preserving source-specific comment kind.
- Do not include Launchpad MPs in GitHub-only metrics such as unresolved review threads unless an equivalent Launchpad concept is verified.
- UI labels should say `Merge Proposals` under Launchpad, while aggregate cards may say `Change Requests` across sources.

## Provider Design

Add `LaunchpadClient` and `LaunchpadProvider`:

- `LaunchpadClient` wraps read-only HTTP calls to Launchpad and rejects non-GET/HEAD methods.
- `LaunchpadProvider.fetch_events()` enumerates configured bug targets and repository targets.
- Bug sync fetches bugs for each bug target, including status, importance, assignee, reporter, milestone, date created, date closed, and web link.
- Repository sync fetches commits, merge proposals, code review comments, and vote references for each repository target.
- Provider output is normalized into `RawEventCreate` or the existing ingestion DTO used by GitHub/Jira.
- Sync state tracks Launchpad bug targets and repository targets independently so a failing repository does not hide successful bug sync.

Testing must use recorded HTTP cassettes for Launchpad API behavior and a real SQLite database for ingestion tests.

## API And UI Behavior

### Datasource Listing

`GET /api/projects` should include Launchpad bug targets and repositories separately:

```json
{
  "id": "launchpad",
  "role": "code",
  "display_name": "Launchpad",
  "bug_targets": ["maas"],
  "repositories": ["~maas-committers/maas/+git/maas-release-tools"]
}
```

If the existing API cannot support typed target fields, add a versioned or additive field while keeping existing project arrays for compatibility.

### Person View

The People page should show Launchpad identities and activity grouped by:

- Bugs reported, assigned, closed, or fixed.
- Commits authored.
- Merge proposals authored or participated in.
- Per-project bug totals and per-repository code totals.

Aggregate cards can combine GitHub PRs and Launchpad MPs under `Change Requests`, but source-specific drill-down must preserve `Pull Requests` and `Merge Proposals` labels.

## Open Questions / Resolved Assumptions

- The config should support separate Launchpad bug targets and repository targets with no association between them.
- MP and PR review mapping should use provider-neutral review concepts for comparable people views.
- Launchpad bugs map to Jira-like work items using configured bug tasks as the primary unit. `Fix Committed` and `Fix Released` count as completed contribution; non-fix terminal states do not count as fixed work.
- A public Launchpad repository useful for API/cassette verification is `https://code.launchpad.net/~maas-committers/maas/+git/maas-release-tools`.
