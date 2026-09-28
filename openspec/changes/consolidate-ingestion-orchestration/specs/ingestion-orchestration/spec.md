## Purpose

Defines consistent, capability-aware selection and execution of provider ingestion work across every supported trigger.

## ADDED Requirements

### Requirement: Provider capability filtering
The system SHALL execute only event types declared as supported by a provider.

#### Scenario: Provider supports a subset of event types
- **WHEN** an ingestion flow selects all work for a provider
- **THEN** the system creates and executes work only for event types in that provider's declared capabilities

#### Scenario: Explicit unsupported event type
- **WHEN** a caller requests an event type that the selected provider does not support
- **THEN** the system rejects the request without creating an ingestion run

### Requirement: Consistent trigger orchestration
The system SHALL use the same target-selection and execution behavior for scheduled, manual, and backfill ingestion.

#### Scenario: Equivalent provider selection across triggers
- **WHEN** scheduled, manual, and backfill flows select the same provider
- **THEN** each flow selects the same supported event types for that provider

### Requirement: Existing ingestion outcomes remain observable
The system SHALL continue recording each attempted supported target as an ingestion run with its trigger, status, event count, and failure details.

#### Scenario: Successful target execution
- **WHEN** a supported provider event fetch and persistence operation succeeds
- **THEN** the corresponding ingestion run records a successful status and the persisted event count

#### Scenario: Failed target execution
- **WHEN** a supported provider event fetch or persistence operation fails
- **THEN** the corresponding ingestion run records a failure status and diagnostic message

### Requirement: Trigger interfaces remain compatible
The system SHALL preserve the existing manual sync HTTP response shape and backfill command result semantics.

#### Scenario: Manual sync succeeds
- **WHEN** a manual sync request executes one or more supported targets
- **THEN** the response contains one existing-format run result for each executed target

#### Scenario: Backfill contains a failure
- **WHEN** at least one supported backfill target fails
- **THEN** the backfill command returns a non-zero result
