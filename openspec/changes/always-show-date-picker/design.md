## Context

`TimeframeSelector` manages three mutually exclusive time modes via URL search params:
- **Preset** (`from`/`to` params derived from a fixed formula, e.g. last 30 days)
- **Sprint** (`sprint_id` param; `from`/`to` absent)
- **Custom** (`from`/`to` params set directly by the user)

Currently the date picker inputs are wrapped in `{!sprintId && ...}`, so they disappear when a sprint is selected. Users lose visibility into what date range a sprint covers and cannot nudge it without switching back to a preset first.

Sprint data is already fetched via `useSprints(project)` and each `SprintResponse` carries `start_date` and `end_date` (ISO datetime strings).

## Goals / Non-Goals

**Goals:**
- Always render the from/to date inputs regardless of the active mode
- When a sprint is selected, pre-fill the date inputs with the sprint's `start_date` and `end_date`
- When the user edits a date input directly, switch to custom mode (clear `sprint_id`, write `from`/`to` to URL, show "Custom" in dropdown)
- Always show the "Custom" option in the dropdown (not conditionally on `fromParam`)

**Non-Goals:**
- Editable sprint boundaries (editing dates while a sprint is shown does NOT update the sprint; it detaches into custom mode)
- Backend or API changes
- Persisting custom ranges beyond URL search params

## Decisions

### Derive displayed dates from active mode, not from URL params alone

When a sprint is selected, `from`/`to` are absent from the URL. Rather than reading the date inputs from URL params only, compute `displayFrom` / `displayTo` as:
- Sprint mode: sprint's `start_date` / `end_date` (truncated to `YYYY-MM-DD`)
- Preset/custom mode: `fromParam` / `toParam` from URL (existing behaviour)

**Alternative considered**: write sprint dates into `from`/`to` when sprint is selected. Rejected because it would pollute the URL and make sprint-vs-preset ambiguous on page load.

### Editing a date input always transitions to custom mode

On any `onChange` from the date inputs, call `setRange(newFrom, newTo)` which already deletes `sprint_id` and sets `from`/`to`. No special-casing needed — existing `setRange` is correct.

The dropdown's `currentValue` already resolves to `'custom'` when `fromParam` is set and no preset matches, so the label updates automatically.

### Always render "Custom" option

Move the `<option value="custom">Custom range</option>` out of the `{fromParam && ...}` guard so it is always present. Selecting it explicitly keeps the current range (existing behavior) or shows empty inputs if no range is set.

## Risks / Trade-offs

- **Sprint dates in date inputs may confuse users** who expect inputs to be read-only for sprints → Mitigation: inputs remain fully editable; editing them naturally detaches from the sprint, which is the intended behavior.
- **Sprint `end_date` may be in the future** for active sprints, which is correct and expected.
- **No sprint found for active `sprint_id`** (e.g. data not yet loaded): inputs show empty strings until data arrives — acceptable transient state.
