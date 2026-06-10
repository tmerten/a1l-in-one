## Why

The dashboard currently shows metrics as static number cards. Cards are useful for a snapshot but hide the story behind the numbers — was this week's drop in commits a fluke or a trend? Did cycle time improve after the team's process change? Are contributions concentrated in one burst or spread evenly?

Time-series charts answer these questions without leaving the dashboard. They let an engineering manager or team lead see at a glance whether a metric is trending up, down, or flat — and zoom in by adjusting the timeframe selector, exactly like Grafana.

The People page has an additional gap: clicking a person today reveals a cramped inline panel below the table. For a meaningful discussion of a person's contributions, a full-page view with proper charts is needed. Charts make individual contribution patterns discussable as one data point in a performance conversation without enabling simplistic cross-person comparison.

## What Changes

- Add **Recharts-powered time-series charts** to the Projects page, one chart per metric section, displayed via a **Cards | Charts** tab toggle on each section.
- Add a **Person detail page** (`/persons/:id`) replacing the current inline expand. Clicking a person navigates to this page.
- The person detail page shows contribution charts for that person across the current timeframe.
- Charts are **Grafana-style**: the timeframe selector drives both range and bucket granularity. No separate zoom control.
- Within each chart, users can **toggle individual series** on/off (e.g., show only PRs and Issues, hide Commits). Toggles reset on navigation.
- Chart type is chosen per metric: stacked bar for volume, multi-line for velocity, bar for collaboration.
- **Combined charts** let related metrics share a chart: Commits + PRs + Issues on one axis, Cycle Time + Review Turnaround on another.

### Chart inventory

| Page | Section | Chart type | Series |
|---|---|---|---|
| Projects | Contribution Volume | Stacked bar | Commits, PRs, Issues (each togglable) |
| Projects | Velocity & Throughput | Multi-line | Cycle Time (median), Review Turnaround (median) |
| Projects | Collaboration | Bar | Reviews per period |
| Person detail | Contribution Volume | Stacked bar | Commits, PRs, Issues |
| Person detail | Velocity | Line | Avg cycle time |
| Person detail | Collaboration | Bar | Reviews per period |

### Person page navigation

| Before | After |
|---|---|
| Click person → inline panel below table | Click person → navigate to `/persons/:id` |
| Constrained width, no charts | Full page, charts + summary cards |
| Back: close panel | Back: browser back / breadcrumb |

## Capabilities

### New Capabilities

- `metric-charts`: Time-series chart components (StackedBarChart, MultiLineChart) backed by existing `/ts` API endpoints. Rendered within a Cards/Charts toggle on each section.
- `person-detail-page`: Full-page person view at `/persons/:id` with contribution charts and summary cards.

### Modified Capabilities

- `dashboard-ui`: Projects page sections gain a tab toggle. Person list rows navigate to person detail page instead of expanding inline.

## Impact

- **Backend**: No changes needed. The `/ts` endpoints and the `/persons/{id}/contributions` endpoint already exist. React hooks calling them already exist.
- **Frontend**: New chart components (Recharts), updated routing, person detail page, toggle UI.
- **Dependencies**: Add `recharts` to `frontend/package.json`.
- **Database**: No changes.

## Scope

```
In scope
─────────────────────────────────────────
• recharts installation
• StackedBarChart and MultiLineChart reusable components
• Cards/Charts tab toggle per section on Projects page
• Three charts on Projects page (volume, velocity, collaboration)
• /persons/:id route and PersonDetailPage
• Three charts on PersonDetailPage (volume, velocity, collaboration)
• Person list rows navigate to detail page
• Series toggles within charts (session-only, no persistence)
• Responsive sizing with the existing layout

Out of scope
─────────────────────────────────────────
• Chart zoom/pan beyond what the timeframe selector provides
• Persisting chart toggle state across navigation
• Export / download charts
• Composition section chart (issue types / PR sizes are categorical, not time-series)
• Sprint burndown chart (different shape — deferred)
• Cross-person comparison charts
```
