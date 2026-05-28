## 1. Datasource Abstraction — Backend

- [x] 1.1 Define `DatasourceRole` enum and `Datasource` Pydantic model in `src/project_health/providers/protocol.py`
- [x] 1.2 Define `SOURCE_CAPABILITIES` dict mapping source IDs to their supported event types (include `issue` and `pull_request_review` for Launchpad alongside `pull_request` and `commit`)
- [x] 1.3 Extend `DataSourceRegistry` with `datasources` property and `build_datasources()` method that constructs `Datasource` objects from config
- [x] 1.4 Update `build_registry()` to populate `datasources` alongside providers
- [x] 1.5 Expose datasources via `app.state` in FastAPI lifespan (alongside existing `config` and `registry`)

## 2. Grouped Projects API Endpoint

- [x] 2.1 Modify `GET /api/projects` to return grouped format with `datasources` array (each entry: `id`, `role`, `display_name`, `projects`)
- [x] 2.2 Add `?format=flat` query param for backward compatibility — returns the old `string[]` format
- [x] 2.3 Update `/api/projects` route handler in `projects.py` to read datasources from `app.state.registry.datasources`
- [x] 2.4 Update OpenAPI types — regenerate `frontend/src/api/types.ts` via `openapi-typescript`

## 3. Person-Centric Aggregation — Backend

- [x] 3.1 Add `person_contributions()` method to `AggregationQueries` — resolves person via `person_identities`, queries `raw_events` across all sources using `(source, actor) IN (identity_pairs)`
- [x] 3.2 Add `_source_filter()` helper to `AggregationQueries` — replaces hard-coded `source = 'github'` with `WHERE source IN (:sources)` driven by `SOURCE_CAPABILITIES` and configured datasources
- [x] 3.3 Refactor existing aggregation queries (`contribution_volume`, `velocity`, `composition`, `collaboration`) to use `_source_filter()` instead of hard-coded source checks
- [x] 3.4 Add `list_persons()` method to `AggregationQueries` — returns all resolved persons with cross-source summary metrics
- [x] 3.5 Add `person_detail()` method — per-person, per-source, per-project breakdown with metric aggregation
- [x] 3.6 Handle unmapped identities (`person_id IS NULL`) in the person-centric path — fallback to `(source, actor)` direct matching
- [x] 3.7 Ensure bot filter applies to person-centric queries (exclude bot actors from person metrics)

## 4. Person-Centric API Endpoints

- [x] 4.1 Create `GET /api/persons` endpoint — returns all resolved persons with summary metrics across all sources; accepts `from`, `to`, `sprint_id`, `datasource`, `project` as narrowing filters
- [x] 4.2 Create `GET /api/persons/{person_id}/contributions` endpoint — detailed per-person, per-datasource, per-project contribution breakdown
- [x] 4.3 Update metrics endpoints to accept `datasource` query param alongside existing `projects` param — `datasource` filters to a specific source type, `project` narrows within
- [x] 4.4 Add Pydantic response models for person endpoints (`PersonSummary`, `PersonContribution`, `DatasourceContribution`, `ProjectContribution`)
- [x] 4.5 Register new routes in `server.py` router setup

## 5. Grouped Project Filter — Frontend

- [x] 5.1 Create `DatasourceProjectFilter` component — accordion-style grouped selector with datasource sections, each listing its projects with "All [source] projects" option
- [x] 5.2 "All sources" top-level option that clears all filters
- [x] 5.3 Single-select within each datasource group (selecting a project within a group selects it; selecting another deselects the previous)
- [x] 5.4 Update URL search params: emit `?datasource=<id>&project=<name>` instead of `?projects=<name>`
- [x] 5.5 Accept legacy `?projects=<name>` param for backward compatibility — map to datasource + project internally
- [x] 5.6 Replace `ProjectFilter` usage in `AppShell` with `DatasourceProjectFilter`
- [x] 5.7 Update `useMetrics` hooks to pass `datasource` and `project` params instead of `projects`

## 6. PeoplePage Redesign — Frontend

- [x] 6.1 Rewrite PeoplePage to fetch from `GET /api/persons` instead of multiple metric endpoints with `?actors=`
- [x] 6.2 PeopleTable columns: Name, Commits, PRs, LOC (+N/−M), Issues Resolved, Reviews, Cycle Time — data from `persons` endpoint
- [x] 6.3 Per-source mini-badges on cell hover (e.g., "GH: 47 commits, Jira: 8 issues")
- [x] 6.4 Row click selects person → shows PersonDetail panel
- [x] 6.5 PersonDetail: PersonHeader with identity badges per datasource (GH: jdoe, Jira: 557058:abc)
- [x] 6.6 PersonDetail: PerDatasourceSections — JiraSection (umbrella role badge, issues by type, per-project breakdown) and GitHubSection (code role badge, commits/PRs/LOC/reviews per repo)
- [x] 6.7 PersonDetail: CrossSourceSummary with totals across all sources
- [x] 6.8 PersonDetail fetches from `GET /api/persons/{person_id}/contributions`
- [x] 6.9 "Clear" button returns to team view (deselects person)
- [x] 6.10 Loading, error, and empty states for the new components

## 7. AppShell Updates

- [x] 7.1 Replace `ProjectFilter` import with `DatasourceProjectFilter` in AppShell
- [x] 7.2 Update `SyncStatusBadge` to show per-datasource sync freshness (each datasource independently)
- [x] 7.3 Propagate `datasource` + `project` filter state from URL params to all child components
- [x] 7.4 Update `useMetrics` hooks and API client to include `datasource` param in requests

## 8. Config Schema Extension

- [x] 8.1 Add `launchpad` section to `ProjectsConfig` Pydantic model (optional, with `base_url` and list of project names)
- [x] 8.2 Add `launchpad` section to `Credentials` Pydantic model (optional, with `oauth_token` env var ref)
- [x] 8.3 Update `build_registry()` to recognize `launchpad` config but skip provider instantiation if `is_configured=False`
- [x] 8.4 Update `project-health.example.yaml` with commented-out Launchpad section
- [x] 8.5 `Datasource(id="launchpad", role=CODE, is_configured=False)` appears in datasources list when Launchpad is declared in config but credentials are missing

## 9. Aggregation Cache Updates

- [x] 9.1 Update cache key to include `datasource` parameter alongside existing query params
- [x] 9.2 Ensure per-source invalidation still works correctly with the new datasource-aware queries
- [x] 9.3 Add cache entries for new person-centric endpoints

## 10. Tests

- [x] 10.1 Test `Datasource` model construction from config — verify role, projects, is_configured for each source
- [x] 10.2 Test `GET /api/projects` grouped format — verify datasource grouping, project lists, role metadata
- [x] 10.3 Test `GET /api/projects?format=flat` backward compatibility — returns flat list
- [x] 10.4 Test `person_contributions()` aggregation — person with identities in both Jira and GitHub returns unified metrics
- [x] 10.5 Test `person_contributions()` for unmapped identity — falls back to source+actor direct match
- [x] 10.6 Test `GET /api/persons` — returns all persons with cross-source metrics; respects timeframe and datasource filters
- [x] 10.7 Test `GET /api/persons/{id}/contributions` — per-source, per-project breakdown
- [x] 10.8 Test `_source_filter()` helper — GitHub-only metrics exclude Jira source; future Launchpad is included when configured
- [x] 10.9 Test bot filter in person-centric queries — bot actors excluded from person metrics
- [x] 10.10 Test `?datasource=jira&project=PROJ` URL params — filters correctly on both backend and frontend
- [x] 10.11 Test backward compatibility: `?projects=PROJ` still works and maps to correct datasource+project
- [x] 10.12 Test Launchpad datasource readiness — Launchpad appears in datasources with `is_configured=False`; no errors; person queries exclude it gracefully; `SOURCE_CAPABILITIES` includes bugs (`issue`) and comments (`pull_request_review`) for Launchpad

## 11. Integration & Polish

- [x] 11.1 End-to-end: select person on People page → see Jira issues + GitHub contributions across repos → clear → team view
- [x] 11.2 Grouped project filter: expand Jira → select project → People page filters to Jira issues only
- [x] 11.3 DatasourceProjectFilter + ProjectsPage interaction — existing project-scoped views still work
- [x] 11.4 Run `ruff check`, `mypy`, `pytest` and `tsc --noEmit` / `vite build`; fix issues