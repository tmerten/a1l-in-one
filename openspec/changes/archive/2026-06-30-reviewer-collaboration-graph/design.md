## Context

The Collaboration section on the Projects page currently shows two views: a "Review Pairs" MetricCard (count of unique reviewers) and a StackedBarChart of total reviews over time. The backend's `GET /api/metrics/collaboration` already returns a `review_matrix` — a nested dict mapping `reviewer -> author -> count` — but the frontend only uses `Object.keys(review_matrix).length` to display the count. The rich pair data is available but unvisualized.

The frontend stack is React 19 + Recharts 3.8.1 + Tailwind CSS 4 + Vite. No graph/network visualization library exists in the project. d3 modules are present as transitive dependencies of Recharts but `d3-force` (the force-directed layout engine) is not included.

## Goals / Non-Goals

**Goals:**
- Render a force-directed network graph where nodes are people and edges represent review collaborations
- Default to undirected edges (A collaborated with B); provide a toggle to show directed edges (A reviewed B)
- Encode edge weight (collaboration frequency) via thickness and a numeric label
- Integrate into the existing Collaboration section as a third view option alongside cards and bar chart
- Work with the existing `review_matrix` API response — no backend changes

**Non-Goals:**
- Backend changes or new API endpoints
- Persisting graph layout positions
- 3D visualization or WebGL rendering
- Filtering individual nodes/edges within the graph (beyond the existing project/timeframe filters)
- Mobile-optimized touch interactions for graph manipulation

## Decisions

### 1. Library choice: `d3-force` + React SVG (not a wrapper library)

Use `d3-force` directly for the force simulation, rendering nodes and edges as React-managed SVG elements.

**Rationale:**
- The graph is small (team-sized: 5–30 nodes). A full graph framework (sigma.js, cytoscape) is overkill.
- `d3-force` is ~8KB gzipped, focused purely on layout computation — no rendering opinions.
- React manages the SVG DOM; d3-force only calculates positions. This avoids the React/d3 DOM ownership conflict.
- Recharts already brings d3 transitive deps; adding `d3-force` keeps the ecosystem consistent.

**Alternatives considered:**
- `react-force-graph-2d` (~100KB, canvas-based) — heavier, canvas rendering conflicts with Tailwind styling approach, harder to style nodes/edges with CSS.
- `@visx/network` — good fit but pulls in the entire visx ecosystem for one component.
- Pure circular/radial layout (no physics) — static layout is less intuitive for understanding cluster patterns; force layout naturally groups frequently-collaborating nodes.

### 2. Three-way view toggle: Cards / Chart / Graph

Extend the existing `collabView` state from `'cards' | 'charts'` to `'cards' | 'charts' | 'graph'`. The `ChartSectionToggle` component gets a third option (graph icon).

**Rationale:**
- The graph complements rather than replaces the bar chart — the chart shows time trends, the graph shows structural relationships.
- Consistent with the existing toggle pattern used across all sections.
- No need for a separate section — keeps the Collaboration section cohesive.

### 3. Undirected as default, directed as toggle within the graph

A small toggle control inside the graph component switches between undirected and directed mode:

- **Undirected (default):** Edges are lines without arrows. Edge weight = sum of reviews in both directions between the pair (A reviewed B + B reviewed A). This answers "how much do these two collaborate?"
- **Directed:** Edges become arrows. If A reviewed B 5 times and B reviewed A 2 times, two separate arrows are shown with their respective counts. This answers "who reviews whom?"

**Rationale:**
- Undirected is simpler to read and directly answers the primary question (collaboration diversity / rotation).
- Directed adds analytical depth for users who want to investigate asymmetric patterns.
- Placing the toggle inside the graph component (not at section level) keeps it contextual and avoids polluting the section-level toggle.

### 4. Edge weight encoding: thickness + label

- **Thickness:** Linearly scaled from 1px (min collaboration count) to 6px (max). Provides instant visual hierarchy.
- **Numeric label:** Small count displayed at the edge midpoint on hover (undirected mode) or near the arrowhead (directed mode). Avoids visual clutter at rest.
- **Color:** Single color (blue-500) for all edges in undirected mode. In directed mode, outgoing edges from hovered node highlight in a distinct color for emphasis.

**Alternatives considered:**
- Color gradient for weight — harder to read with many overlapping edges, less accessible.
- Always-visible labels — too cluttered for graphs with 10+ edges.

### 5. Node representation

- Nodes are circles with initials (first letter of display name) or avatar if available.
- Node size is fixed (not scaled by degree) — the edges carry the analytical signal, not the nodes.
- Person's display name appears on hover as a tooltip.
- Nodes are draggable (standard d3-force interaction) for manual layout adjustment.

### 6. Data transformation from review_matrix

The `review_matrix` shape `{reviewer: {author: count}}` is transformed client-side into graph data:

```typescript
// Undirected: merge bidirectional pairs
{A: {B: 3}, B: {A: 2}} → edge(A, B, weight=5)

// Directed: keep separate
{A: {B: 3}, B: {A: 2}} → edge(A→B, weight=3), edge(B→A, weight=2)
```

Nodes are derived from the union of all keys in the matrix (both reviewers and authors). Person display names come from `per_person` in the same API response, falling back to the raw actor ID.

### 7. Empty and minimal states

- **No data:** Show placeholder text "No collaboration data for this period" (consistent with other empty states).
- **Single node:** Show the node without edges — edge case when only one person has review activity.
- **Very dense graph (>20 nodes):** The force simulation handles this naturally with repulsion forces. No special capping needed for team-sized data.

## Risks / Trade-offs

- **[Risk] Force simulation jitter on re-render** → Mitigation: Initialize simulation once on data change, not on every React render. Use `useRef` for simulation instance; update only when `review_matrix` changes. Stop simulation after convergence (alpha < 0.01).
- **[Risk] Overlapping edges in directed mode between same pair** → Mitigation: Offset parallel directed edges with a small arc/curve so A→B and B→A are visually distinct.
- **[Trade-off] No backend person resolution for node labels** → The `review_matrix` uses actor IDs (GitHub usernames), not resolved person display names. The `per_person` dict from the same endpoint provides some mapping but may not have full display names. Acceptable for v1; could enhance later by cross-referencing the persons API.
- **[Trade-off] `d3-force` is an additional dependency** → ~8KB gzipped, purpose-built, no alternatives that are smaller for force-directed layout. The benefit clearly outweighs the cost.
- **[Trade-off] SVG rendering limits at scale** → For teams of 50+ people the graph could become cluttered. This is acceptable for the target use case (team-level, 5-30 people). A threshold warning or automatic simplification could be added later.
