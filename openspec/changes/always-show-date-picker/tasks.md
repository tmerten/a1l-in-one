## 1. Update TimeframeSelector component

- [x] 1.1 Compute `displayFrom` and `displayTo` derived values: when `sprintId` is active, look up the sprint in the loaded sprints list and use its `start_date`/`end_date` (truncated to `YYYY-MM-DD`); otherwise fall back to `fromParam`/`toParam`
- [x] 1.2 Remove the `{!sprintId && ...}` conditional wrapping the date picker inputs so they always render
- [x] 1.3 Bind the date inputs to `displayFrom`/`displayTo` instead of `fromParam`/`toParam` directly
- [x] 1.4 Move the "Custom range" `<option>` out of the `{fromParam && ...}` guard so it is always present in the dropdown
- [x] 1.5 Update the `onChange` handler for both date inputs to call `setRange` with the new value and the current `displayFrom`/`displayTo` as the other half (so editing one input preserves the other date, even when switching out of sprint mode)

## 2. Verify behaviour

- [x] 2.1 Selecting a preset: date inputs show the preset's computed dates; editing either input switches dropdown to "Custom"
- [x] 2.2 Selecting a sprint: date inputs show the sprint's start and end dates; editing either input clears `sprint_id`, sets `from`/`to`, and switches dropdown to "Custom"
- [x] 2.3 "Custom" option is visible in the dropdown before any manual date edit has been made
- [x] 2.4 Selecting "Custom" from the dropdown while a preset is active keeps the currently displayed dates
