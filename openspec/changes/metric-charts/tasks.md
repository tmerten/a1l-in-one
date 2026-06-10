## 1. Install Recharts

- [x] 1.1 Add `recharts` to `frontend/package.json` dependencies and run `npm install` in the `frontend/` directory
- [x] 1.2 Verify TypeScript types are available (`recharts` 2.x ships its own types — confirm no `@types/recharts` needed)

## 2. Shared Chart Components

- [x] 2.1 Create `frontend/src/components/StackedBarChart.tsx` — accepts `data`, `series` (with `key`, `label`, `color`, `visible`), `onToggle`, `bucketSize`; renders `<ResponsiveContainer height={220}>` with `<BarChart>`, one `<Bar>` per series, `<XAxis>` with bucket-formatted ticks, `<Tooltip>`, and a clickable legend row above the chart
- [x] 2.2 Create `frontend/src/components/MultiLineChart.tsx` — same props shape as `StackedBarChart` plus optional `unit` for tooltip suffix; renders `<LineChart>` with `connectNulls`, dots hidden at large datasets, same legend pattern
- [x] 2.3 Create `frontend/src/components/ChartSectionToggle.tsx` — pill toggle (Cards | Charts) rendered at the right of a section header; accepts `value: "cards" | "charts"` and `onChange`
- [x] 2.4 Add x-axis tick formatter utility `frontend/src/lib/formatBucket.ts` — formats ISO date strings by `bucketSize`: `"day"` → `"Jun 3"`, `"week"` → `"W23"`, `"month"` → `"Jun 2026"`

## 3. Projects Page — Contribution Volume Chart

- [x] 3.1 In `ProjectsPage.tsx`, add `useState<"cards" | "charts">` for the volume section toggle (default: `"cards"`)
- [x] 3.2 Add `useContributionVolumeTs(query)` call alongside the existing `useContributionVolume(query)`
- [x] 3.3 Add series toggle state: `useState({ commits: true, prs: true, issues: true })`
- [x] 3.4 Render `<ChartSectionToggle>` in the Contribution Volume section header
- [x] 3.5 When toggle is `"charts"`, render `<StackedBarChart>` with data mapped from `contributionVolumeTs` response (`bucket` → x, `value.commits` / `value.prs` / `value.issues` → series), passing series visibility state and `onToggle`
- [x] 3.6 Handle loading (skeleton) and empty states in the chart view

## 4. Projects Page — Velocity Chart

- [x] 4.1 Add `useState<"cards" | "charts">` for the velocity section toggle
- [x] 4.2 Add `useVelocityTs(query)` call
- [x] 4.3 Add series toggle state: `useState({ cycle_time: true, review_turnaround: true })`
- [x] 4.4 Note: `velocity/ts` returns `avg_cycle_hours` per bucket; `review_turnaround` is not yet in the `/ts` response — use only `avg_cycle_hours` for the line and label it "Avg Cycle Time (hrs)" in v1. (Review turnaround time-series is out of scope until the backend adds it.)
- [x] 4.5 Render `<ChartSectionToggle>` and `<MultiLineChart>` with `unit="hrs"` in the velocity section

## 5. Projects Page — Collaboration Chart

- [x] 5.1 Add `useState<"cards" | "charts">` for the collaboration section toggle
- [x] 5.2 Add `useCollaborationTs(query)` call
- [x] 5.3 Render `<ChartSectionToggle>` and `<StackedBarChart>` (single series: `reviews`) in the collaboration section — no series toggle needed when only one series

## 6. Person Detail Page — Routing

- [x] 6.1 Add route `<Route path="/persons/:personId" element={<PersonDetailPage />} />` to `frontend/src/router.tsx`
- [x] 6.2 Create `frontend/src/pages/PersonDetailPage.tsx` (empty shell that renders "Person detail" and `personId` from `useParams()` — fills out in task 7)
- [x] 6.3 In `PeoplePage.tsx`, change the person row `onClick` handler from expanding the inline panel to `navigate(\`/persons/${person.id}\`)`
- [x] 6.4 Remove the inline person detail panel from `PeoplePage.tsx` (the expanded area below the table)

## 7. Person Detail Page — Content

- [x] 7.1 Fetch person contributions via `usePersonContributions(personId, query)` (already exists)
- [x] 7.2 Extract GitHub `external_id` from person identities: `person.identities.find(i => i.source === "github")?.external_id` — use as the `actors` filter for chart hooks
- [x] 7.3 Call `useContributionVolumeTs({ ...query, actors: [githubLogin] })`, `useVelocityTs(...)`, `useCollaborationTs(...)` for chart data
- [x] 7.4 Render page header: back link ("← People"), person display name, identity badge(s)
- [x] 7.5 Render summary cards row (4 cards): Commits, PRs Merged, Issues Resolved, Reviews — values from `usePersonContributions` aggregate totals
- [x] 7.6 Render "Contribution Volume over time" section with `<StackedBarChart>` and series toggles (commits/PRs/issues)
- [x] 7.7 Render "Velocity over time" section with `<MultiLineChart>` (avg cycle time, unit="hrs")
- [x] 7.8 Render "Collaboration over time" section with `<StackedBarChart>` (reviews, single series)
- [x] 7.9 Handle case where person has no GitHub identity: show summary cards from contributions data but display "Chart data not available — no GitHub identity" in place of charts
- [x] 7.10 Handle loading, error, and not-found states

## 8. Tests

- [x] 8.1 Test `formatBucket` utility — "day" format, "week" format, "month" format; edge cases (year boundary)
- [x] 8.2 Test `StackedBarChart` renders correct number of bars and respects `visible: false` on a series
- [x] 8.3 Test `ChartSectionToggle` — clicking "Charts" calls `onChange("charts")`, clicking "Cards" calls `onChange("cards")`
- [x] 8.4 Test `PersonDetailPage` — renders person name, renders charts when GitHub identity present, renders fallback message when no GitHub identity
- [x] 8.5 Test person row click in `PeoplePage` navigates to `/persons/:id` instead of expanding inline

## 9. Polish & Verification

- [ ] 9.1 Verify charts resize correctly when the browser window is resized (ResponsiveContainer)
- [ ] 9.2 Verify timeframe changes (e.g. switching from "last 7 days" to "last 90 days") update chart data and x-axis tick format
- [ ] 9.3 Verify series toggles work — hiding all series shows an empty chart (not a crash)
- [ ] 9.4 Verify person page back navigation returns to correct People page URL with existing filters
- [x] 9.5 Run `tsc --noEmit` and `vite build` in `frontend/` — resolve all type errors
- [x] 9.6 Run `ruff check` and `pytest` — no regressions (no backend changes, but verify)
