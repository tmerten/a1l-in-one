## 1. Event Vocabulary and Capabilities

- [x] 1.1 Add the typed event registry and verify every existing persisted event type has fetch and write dispatch coverage
- [x] 1.2 Declare capabilities for each built-in provider and verify target selection excludes unsupported provider/event combinations

## 2. Shared Orchestration

- [x] 2.1 Implement the ingestion service for target validation and execution and verify successful and failed runs retain their existing database outcomes
- [x] 2.2 Migrate scheduled ingestion to the shared service and verify jobs are registered only for supported targets
- [x] 2.3 Migrate manual sync to the shared service and verify response and unsupported-request behavior through API tests
- [x] 2.4 Migrate backfill to the shared service and verify provider filtering, event counts, and exit-code behavior

## 3. Validation

- [x] 3.1 Remove obsolete duplicated dispatch and target lists, then run Ruff and mypy over the changed backend modules
- [x] 3.2 Run the focused ingestion and API tests, then run the complete backend test suite
