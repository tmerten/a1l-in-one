## Why

Ingestion orchestration is duplicated across scheduled, manual, and backfill entry points, and each path attempts every event type for every provider. This causes unsupported no-op runs, redundant provider requests, and inconsistent behavior as providers and event types evolve.

## What Changes

- Define provider capabilities as the source of truth for supported event types.
- Introduce a shared ingestion service used by scheduler, manual sync, and backfill flows.
- Dispatch ingestion through typed event handlers instead of duplicated string-based conditionals.
- Ensure each orchestration flow runs only event types supported by the selected provider.
- Preserve existing API responses, persistence semantics, retry behavior, and scheduling behavior.
- Add focused tests for capability filtering and shared orchestration while updating only tests coupled to the old structure.

## Capabilities

### New Capabilities

- `ingestion-orchestration`: Defines capability-aware ingestion target selection and consistent execution across scheduled, manual, and backfill triggers.

### Modified Capabilities

None.

## Impact

The change affects provider contracts and registry metadata, ingestion scheduling and execution, the manual sync route, the backfill CLI, and their focused tests. It does not change external provider write behavior, HTTP response schemas, database schemas, frontend behavior, or dependencies.
