## Why

The dashboard shows review collaboration as a single number (review pair count) and a bar chart of total reviews over time. The `review_matrix` data — who reviews whom and how often — is already computed by the backend but not visualized. An engineering manager cannot see whether collaboration is well-distributed across the team or concentrated between a few recurring pairs. A network graph makes reviewer rotation (or lack thereof) immediately visible, answering: "Do we have healthy collaboration diversity, or are the same 2-3 people always reviewing each other?"

## What Changes

- Add a **collaboration network graph** component that renders reviewers and authors as nodes and their collaboration relationships as edges.
- Edges are **undirected by default** (A collaborated with B), with a **toggle to switch to directed mode** (A reviewed B's code, shown with arrows).
- Edge thickness and/or a numeric label indicates collaboration frequency (number of reviews between the pair).
- The graph uses the existing `review_matrix` data from `GET /api/metrics/collaboration` — no new backend endpoints needed.
- The graph respects the current timeframe and project filters, so it shows collaboration patterns for the selected period.
- Integrate into the existing Collaboration section on the Projects page alongside the current bar chart.

## Capabilities

### New Capabilities

- `collaboration-network-graph`: A force-directed network graph visualization showing reviewer-author relationships as nodes and edges, with undirected/directed toggle, edge weight indicators, and integration with existing collaboration metrics data.

### Modified Capabilities

## Impact

- **Frontend**: New graph component added to the Collaboration section. Requires adding a graph visualization library (e.g., `@react-force-graph`, `d3-force` directly, or similar). No changes to existing components — the graph is additive.
- **Backend/API**: No changes. The existing `GET /api/metrics/collaboration` endpoint already returns the `review_matrix` (reviewer -> author -> count) that provides the edge data.
- **Dependencies**: One new frontend npm dependency for force-directed graph rendering.
- **Database**: No changes.
