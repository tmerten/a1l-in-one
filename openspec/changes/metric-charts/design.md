## Context

The backend already exposes three time-series endpoints:
- `GET /api/metrics/contribution-volume/ts` → `{ bucket_size, data: [{ bucket, value: { commits, prs, issues } }] }`
- `GET /api/metrics/velocity/ts` → `{ bucket_size, data: [{ bucket, value: { avg_cycle_hours } }] }`
- `GET /api/metrics/collaboration/ts` → `{ bucket_size, data: [{ bucket, value: { reviews } }] }`

The React hooks `useContributionVolumeTs`, `useVelocityTs`, and `useCollaborationTs` in `frontend/src/hooks/useMetrics.ts` already call these endpoints. The frontend has never rendered their results — adding charts is a pure frontend change.

The person detail endpoint `GET /api/persons/{person_id}/contributions` already exists and is called by `usePersonContributions`. The person list page currently expands inline; the routing change to `/persons/:id` is also a frontend-only change.

## Goals / Non-Goals

**Goals:**
- Render time-series data as Recharts charts on Projects page and Person detail page
- Add Cards/Charts tab toggle per metric section
- Navigate to a full person detail page on row click
- Series toggles within charts; no persistence required

**Non-Goals:**
- Any backend changes
- Chart zoom beyond timeframe selector
- Composition section charts (categorical data, not time-series)
- Sprint burndown chart
- Cross-person comparison

## Decisions

### 1. Recharts as the charting library

Recharts is the natural choice for this stack: composable React components, TypeScript support, responsive containers built-in, and no CSS framework conflicts with Tailwind. The project has no existing chart library. Tremor was considered but requires too much of its own design system; Nivo is heavier than needed.

Installation: `recharts` + `@types/recharts` (if not bundled — Recharts 2.x ships its own types).

### 2. Two reusable chart components

Rather than per-metric chart components, two generic components cover all cases:

**`StackedBarChart`** — for volume data where multiple series stack to a total:
```
Props:
  data: Array<{ bucket: string; [key: string]: number | string }>
  series: Array<{ key: string; label: string; color: string; visible: boolean }>
  onToggle: (key: string) => void
  bucketSize: string   // "day" | "week" | "month" — for x-axis tick formatting
```

**`MultiLineChart`** — for rate/latency data where series are independent:
```
Props:
  data: Array<{ bucket: string; [key: string]: number | string | null }>
  series: Array<{ key: string; label: string; color: string; visible: boolean }>
  onToggle: (key: string) => void
  bucketSize: string
  unit?: string        // e.g. "hrs" for tooltip suffix
```

Both components:
- Wrap in `<ResponsiveContainer width="100%" height={220} />`
- Render a legend at the top where clicking a label toggles that series (series toggle lives in the parent component's state)
- Format x-axis ticks based on `bucketSize`: day → "Jun 3", week → "W23", month → "Jun"
- Show a `<Tooltip>` with formatted values

### 3. Cards/Charts toggle per section

Each metric section on the Projects page gets a two-option toggle (Cards | Charts) rendered as a pill at the right of the section header:

```
Contribution Volume                    [Cards] [Charts]
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Commits     │ │  PRs         │ │ Issues       │ │ Issues       │
│   128        │ │   34         │ │  Opened 12   │ │ Resolved 9   │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘

— vs —

Contribution Volume                    [Cards] [Charts]
▐ Commits  ▐ PRs  ▐ Issues
▁▂▅▇▅▃▂▁▄▂▅▇▆▃▂ (stacked bar)
```

Toggle state lives in component-local `useState` — no URL encoding, no localStorage. Resets on navigation. The toggle only appears on sections that have a time-series equivalent. (Composition and Burndown sections do not get the toggle in v1.)

### 4. Person detail page — routing

New route: `/persons/:personId`

The existing `router.tsx` gets a new `<Route path="/persons/:personId" element={<PersonDetailPage />} />`. The existing person list row's `onClick` changes from expanding inline to `navigate(\`/persons/${person.id}\`)`.

`PersonDetailPage` reads `personId` from `useParams()`, fetches contributions via `usePersonContributions`, and also fetches the person's time-series data by passing `actors: [personId]` to the `/ts` endpoints.

Wait — the `/ts` endpoints accept `actors` as a filter. The hooks already support this. So a person's charts are just the same `useContributionVolumeTs`, `useVelocityTs`, `useCollaborationTs` hooks with `actors: [person.identity.external_id]` added to the query. No new endpoints needed.

**Person identity resolution**: The `PersonContributions` response includes the person's identities per source. The frontend needs to pass the right `actor` value for each source filter. For a person with `{ source: "github", external_id: "jdoe" }`, the actor param is `jdoe`. Since the `/ts` endpoints already accept `actors[]`, this works.

Actually, looking at the existing API, `GET /api/persons/{person_id}/contributions` returns the person's data already aggregated. For time-series on the person page, the cleanest approach is to pass `actors=[externalId]` to the existing `/ts` endpoints — the backend already filters by actor. The person's GitHub login is their actor in raw_events.

### 5. Person detail page layout

```
/persons/:id
───────────────────────────────────────────────────────────
← Back to People       [Alice Johnson]  @alicejohnson · alice@company.com

Summary cards (4 across)
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  Commits │ │    PRs   │ │ Issues   │ │ Reviews  │
│   128    │ │    34    │ │  Res. 9  │ │    41    │
└──────────┘ └──────────┘ └──────────┘ └──────────┘

Contribution Volume over time
[Commits ✓] [PRs ✓] [Issues ✓]          ← series toggles
▁▂▅▇▅▃▂▁▄▂▅▇▆▃▂ (stacked bar)

Velocity over time
[Cycle Time ✓] [Review Turnaround ✓]
 ─────╮╭─────╮                          (multi-line)

Collaboration over time
▁▃▅▃▁▂▄▃▁ (bar)
───────────────────────────────────────────────────────────
```

The summary cards come from `usePersonContributions` (aggregate totals). The charts come from the `/ts` hooks with actor filter. Both share the same timeframe from URL params.

### 6. Series color palette

Consistent colors across all charts:

| Series | Color |
|---|---|
| Commits | `#6366f1` (indigo) |
| PRs | `#10b981` (emerald) |
| Issues | `#f59e0b` (amber) |
| Reviews | `#3b82f6` (blue) |
| Cycle Time | `#8b5cf6` (violet) |
| Review Turnaround | `#ec4899` (pink) |

### 7. Empty and loading states

- Loading: chart area shows a grey skeleton placeholder (same height as the chart)
- Empty (no data points): show "No data for this timeframe" centered in the chart area
- Error: show the existing error style from `MetricCard`

## Risks / Trade-offs

- **[Trade-off] Actor filter for person charts uses GitHub login, not person_id** → The `/ts` endpoints filter by `actor` (raw event actor), not by `person_id`. For a person with multiple identities (GitHub + Jira), the time-series only covers the GitHub actor. This is acceptable for v1 since all time-series data comes from GitHub events. A `person_id`-aware `/ts` endpoint would be the v2 improvement.
- **[Trade-off] Toggle state not persisted** → Users who switch between Cards and Charts views or navigate away lose their toggle preference. Agreed non-goal for v1.
- **[Risk] Bucket size mismatch** → If the user has a very long timeframe (e.g. 6 months), bucket size becomes "week" or "month" automatically. The charts should handle sparse data gracefully — Recharts does this well with `connectNulls` on line charts.
- **[Risk] Person page actor resolution for multi-source persons** → If a person's GitHub login differs from their display name, the actor filter must use the correct external_id. The person contributions response contains identities — extract `external_id` where `source === "github"` for the actor filter.
