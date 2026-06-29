## Why

The dashboard currently observes work through GitHub and Jira, but the team also uses Canonical Launchpad for code review, source repositories, and bug tracking. Without Launchpad ingestion, the dashboard undercounts engineering activity and misses a major part of how work moves from reported bug to reviewed change.

Launchpad does not fit the existing GitHub-shaped assumptions cleanly:

- Launchpad repositories are not necessarily owned by a project. They can be associated with people or teams, while bugs are associated with projects.
- Launchpad merge proposals are similar to pull requests but do not expose the same review comment and resolution model available from GitHub.
- A single Launchpad project may need bug observation while related code work happens across multiple Bazaar/Git repositories owned by teams or individuals.

This change adds Launchpad as a first-class observed platform while preserving the existing person-centric, datasource-aware model. It also makes the configuration shape explicit enough to represent Launchpad bugs and repositories without forcing an inaccurate one-to-one project-to-repository mapping.

## What Changes

- Add a Launchpad provider that reads bugs, repositories, commits, and merge proposals from Launchpad using read-only API access.
- Extend configuration to support Launchpad bug targets and repository targets independently. Launchpad bugs are treated like Jira-style work items; Launchpad repositories are treated like GitHub-style code repositories.
- Map Launchpad bugs into the existing issue/work-item model while preserving Launchpad-specific fields needed for status, importance, assignee, milestone, and project.
- Map both GitHub pull requests and Launchpad merge proposals into a provider-neutral change request and review model so people views remain comparable across platforms.
- Extend identity resolution so Launchpad people and teams can be associated with existing dashboard persons.
- Add Launchpad datasource metadata, sync health, metrics aggregation, and UI drill-downs alongside GitHub and Jira.

## Configuration Direction

The proposed direction is fully decoupled Launchpad configuration:

```yaml
launchpad-bugs:
  - maas

launchpad-repos:
  - ~maas-committers/maas-ci/+git/maas-ci-internal
  - ~maas-committers/maas-images/+git/maas-v3-streams-candidate-signed
  - ~maas-committers/maas/+git/maas-release-tools
```

This avoids creating a false association between Launchpad projects and repositories. Launchpad bugs belong to bug targets/projects and should be comparable to Jira tickets. Launchpad repositories belong to people or teams and should be comparable to GitHub repositories.

The design explains the alternatives and tradeoffs:

- Fully decoupled `launchpad_bugs` and `launchpad_repos` lists.
- Fully hierarchical project-first configuration.
- Hybrid project groups plus standalone repositories.

The selected direction is fully decoupled. Any cross-view grouping should happen through dashboard filters or reporting configuration later, not through Launchpad ingestion configuration.

## Capabilities

### New Capabilities

- `launchpad-observation`: Launchpad API ingestion for bugs, repositories, commits, merge proposals, review decisions, review comments, people, and teams.
- `launchpad-config`: Configuration model for Launchpad project bug targets and repository targets that are not assumed to have a one-to-one relationship.
- `change-request-abstraction`: Provider-neutral representation for GitHub PRs and Launchpad merge proposals, including comparable review requests, review decisions, and review comments with source-specific detail preserved.

### Modified Capabilities

- `data-ingestion`: Register and schedule Launchpad sync jobs alongside GitHub and Jira while preserving read-only provider constraints.
- `metrics-aggregation`: Include Launchpad bugs, commits, and merge proposals in person, project, and datasource-scoped metrics.
- `dashboard-ui`: Show Launchpad as a datasource with bug and repository groups, Launchpad sync status, and Launchpad-specific MP detail.
- `identity-resolution`: Support Launchpad people/team identities linked to dashboard persons.

## Impact

- **Database**: Requires migrations for provider-neutral change request and review interaction events, with raw source payloads preserved for both GitHub and Launchpad.
- **API**: Existing person and metrics endpoints gain Launchpad source values. Project/source listing gains Launchpad bug targets and repository groups.
- **Frontend**: Datasource filter and person drill-down gain Launchpad sections. MP detail uses shared change-request/review concepts while preserving source-specific Launchpad labels.
- **Providers**: New Launchpad client and provider, using recorded HTTP cassettes in tests and enforcing read-only HTTP methods.
- **Configuration**: Adds `launchpad` config with project bug targets and repository targets.

## Non-Goals

- Writing to Launchpad, GitHub, or Jira.
- Perfectly equating Launchpad merge proposals with GitHub pull requests at the source level. They are mapped to shared concepts for comparable people metrics while preserving source-specific details.
- Inferring a single Launchpad project for every repository when Launchpad ownership does not provide that relationship.
- Implementing cross-provider issue linking heuristics beyond storing explicit references observed in raw data.
