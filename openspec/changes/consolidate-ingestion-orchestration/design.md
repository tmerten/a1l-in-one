## Context

Provider capabilities exist in `providers/protocol.py`, but scheduler, manual sync, and backfill each maintain their own event-type lists and orchestration loops. `IngestionRunner` separately dispatches fetch and write behavior through string conditionals. Providers implement unsupported protocol methods as empty results, so incorrect target selection appears successful and produces misleading ingestion records.

The application is a local single-process service using async SQLAlchemy sessions and an in-process APScheduler. Existing API and database contracts must remain stable.

## Goals / Non-Goals

**Goals:**

- Establish one typed event-type vocabulary and provider capability source.
- Share target selection and execution across all ingestion triggers.
- Keep transaction, retry, run-recording, and provider behavior stable.
- Make adding an event type require one dispatch registration rather than edits across entry points.

**Non-Goals:**

- Redesign provider HTTP request batching.
- Change raw-event or ingestion-run schemas.
- Move scheduling out of process.
- Change API response models or frontend behavior.

## Decisions

### Use a typed event registry

Define an `EventType` string enum and an ordered event definition registry. Each definition owns its fetch and write dispatch behavior. This preserves database string values while removing parallel conditional chains.

An enum plus registry is preferred over provider-specific orchestration because persistence behavior remains common and the complete event vocabulary stays discoverable in one place.

### Declare capabilities on provider implementations

Each provider exposes an immutable capability set using the shared event type. The existing source-level capability mapping remains available for aggregation filtering but is derived from the same declarations, preventing orchestration and reporting metadata from drifting.

Explicit capabilities are preferred over detecting method existence because the protocol currently requires all fetch methods and unsupported providers intentionally implement no-op methods.

### Introduce an ingestion service above individual runs

An `IngestionService` selects targets, validates explicit requests, creates sessions, and delegates each selected target to `IngestionRunner`. Scheduler, manual sync, and backfill use this service instead of maintaining event lists and loops.

`IngestionRunner` remains responsible for one target's durable run record, retry, fetch, and write lifecycle. This keeps the behavioral change small and preserves focused unit boundaries.

### Keep trigger-specific presentation outside the service

The service returns `IngestionRun` results. HTTP response conversion, CLI output, scheduler logging, lock handling, and trigger-specific failure presentation remain in their adapters.

This avoids coupling application orchestration to FastAPI, Typer, or APScheduler.

## Risks / Trade-offs

- **[Provider capability declarations can be incorrect]** → Add tests that compare declared capabilities with selected targets and cover all built-in providers.
- **[Changing string event types can affect persisted data]** → Use a string enum whose values exactly match the existing database values.
- **[Shared execution could alter failure propagation]** → Preserve `IngestionRunner` result semantics and let each adapter retain its current response or exit handling.
- **[Existing tests may depend on unsupported no-op runs]** → Update only tests that assert obsolete target selection; retain storage and aggregation tests unchanged.

## Migration Plan

1. Add the typed event registry, provider declarations, and service without database changes.
2. Switch backfill, manual sync, and scheduler adapters to the service.
3. Remove duplicated event lists and conditional dispatch.
4. Run focused ingestion, sync API, and backfill tests, followed by the backend suite.

Rollback consists of restoring the prior adapter loops and runner dispatch; no persisted-data migration is involved.
