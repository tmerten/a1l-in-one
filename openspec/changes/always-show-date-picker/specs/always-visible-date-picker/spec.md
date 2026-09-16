## ADDED Requirements

### Requirement: Date picker is always visible
The timeframe selector SHALL display from and to date inputs at all times, regardless of whether a preset, sprint, or custom range is the active selection.

#### Scenario: Date picker visible with preset selected
- **WHEN** a relative preset (e.g. "Last 30 days") is selected in the dropdown
- **THEN** the from and to date inputs are rendered and show the computed preset dates

#### Scenario: Date picker visible with sprint selected
- **WHEN** a sprint is selected in the dropdown
- **THEN** the from and to date inputs are rendered and show the sprint's start and end dates

#### Scenario: Date picker visible with custom range active
- **WHEN** a custom date range is active
- **THEN** the from and to date inputs are rendered and show the custom from and to dates

### Requirement: Editing a date input switches to custom mode
When the user modifies either date input, the selector SHALL switch to custom mode: the `sprint_id` URL param is cleared, the `from` and `to` URL params are set to the new values, and the dropdown displays "Custom".

#### Scenario: User edits from-date while preset is active
- **WHEN** a preset is active and the user changes the from date input
- **THEN** the `from` URL param is updated, `sprint_id` is absent, and the dropdown shows "Custom"

#### Scenario: User edits to-date while sprint is active
- **WHEN** a sprint is selected and the user changes the to date input
- **THEN** the `sprint_id` URL param is removed, the `from` and `to` params reflect the sprint's start date and the new to date, and the dropdown shows "Custom"

### Requirement: Custom option is always present in the dropdown
The "Custom" option SHALL always appear in the timeframe dropdown, not only when a custom range is already active.

#### Scenario: Custom option visible before any manual date edit
- **WHEN** only preset or sprint options have been used and no custom range has been set
- **THEN** the "Custom" option is still present in the dropdown

#### Scenario: Selecting Custom keeps current range
- **WHEN** the user selects "Custom" from the dropdown while a preset or sprint is active
- **THEN** the date inputs retain the currently displayed dates and the dropdown shows "Custom"
