## Why

When a sprint is selected in the timeframe dropdown, the date picker disappears, leaving users unable to see or adjust the effective date range. Always showing the date pickers gives users a consistent reference point and lets them fine-tune any selection — preset, sprint, or custom — without switching modes.

## What Changes

- The date picker inputs (from/to) are always visible, regardless of whether a sprint or a preset is selected
- When a sprint is active, the date inputs are pre-filled with the sprint's start and end dates (read-only display or editable to override)
- When the user manually edits either date input, the dropdown switches to show "Custom" and clears any active sprint or preset binding
- The "Custom range" option in the dropdown is always present (not conditionally rendered)

## Capabilities

### New Capabilities

- `always-visible-date-picker`: Date picker inputs are always rendered in the timeframe selector; editing them sets a custom date range and marks the dropdown as "Custom"

### Modified Capabilities

<!-- No existing specs are changing requirements -->

## Impact

- `frontend/src/components/TimeframeSelector.tsx`: primary change — remove the `!sprintId` conditional wrapping the date picker, populate date inputs from sprint data when a sprint is selected, and wire date changes to clear sprint/preset and set "custom"
- No backend or API changes required
