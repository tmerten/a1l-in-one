## 1. Dependencies & Setup

- [x] 1.1 Add `d3-force` and `@types/d3-force` to frontend dependencies
- [x] 1.2 Verify d3-force types work with the project's TypeScript config (`tsc --noEmit`)

## 2. Data Transformation Layer

- [x] 2.1 Create `frontend/src/lib/graphData.ts` — transform `review_matrix` into graph node/edge structures: `buildUndirectedGraph(matrix)` and `buildDirectedGraph(matrix)` functions
- [x] 2.2 Undirected mode: merge bidirectional pairs (A→B: 3, B→A: 2 becomes A-B: 5), deduplicate nodes from all reviewer and author keys
- [x] 2.3 Directed mode: keep separate edges with direction metadata, handle self-referential edge case
- [x] 2.4 Compute edge weight scale (min/max for thickness mapping, 1px–6px range)

## 3. Force Simulation Hook

- [x] 3.1 Create `frontend/src/hooks/useForceGraph.ts` — custom hook that manages d3-force simulation lifecycle (init, update on data change, stop on unmount)
- [x] 3.2 Configure forces: center, charge (repulsion), link (edge-based attraction), collision prevention
- [x] 3.3 Return stable node positions via `useRef` + tick-based state updates (avoid re-render per tick — batch with requestAnimationFrame)
- [x] 3.4 Support node dragging: pin dragged node position, reheat simulation on drag start, fix position on drag end

## 4. CollaborationGraph Component

- [x] 4.1 Create `frontend/src/components/CollaborationGraph.tsx` — SVG-based graph renderer consuming positions from `useForceGraph`
- [x] 4.2 Render nodes as circles with single-letter initials (first character of display name, fallback to actor ID)
- [x] 4.3 Render undirected edges as `<line>` elements with stroke-width proportional to weight
- [x] 4.4 Render directed edges as `<line>` with arrowhead markers (`<marker>` SVG defs), offset parallel edges between same pair using a slight arc (`<path>` with quadratic curve)
- [x] 4.5 Add directed/undirected toggle control inside the graph component (small pill toggle above the SVG)
- [x] 4.6 Implement hover tooltip on nodes — show full display name from `per_person` data
- [x] 4.7 Implement hover on edges — show numeric weight label at edge midpoint
- [x] 4.8 Handle empty state: show "No collaboration data for this period" message when review_matrix is empty
- [x] 4.9 ResponsiveContainer: size SVG to parent width, fixed aspect ratio (e.g., 4:3), re-center simulation on resize

## 5. Integration into ProjectsPage

- [x] 5.1 Extend `collabView` state type from `'cards' | 'charts'` to `'cards' | 'charts' | 'graph'`
- [x] 5.2 Add graph icon option to `ChartSectionToggle` component (or create a variant that supports 3 options)
- [x] 5.3 Render `CollaborationGraph` in the collaboration section when `collabView === 'graph'`, passing `collaboration?.review_matrix` and `collaboration?.per_person`
- [x] 5.4 Ensure the graph uses the same loading/error patterns as cards and charts views

## 6. Styling & Polish

- [x] 6.1 Style nodes: bg-blue-500 fill, white text for initials, subtle drop shadow, hover ring
- [x] 6.2 Style edges: gray-400 stroke (undirected), blue-500 stroke for directed, opacity for less-weighted edges
- [x] 6.3 Style tooltip: small floating div with person name or edge weight, consistent with existing MetricCard tooltip styling
- [x] 6.4 Ensure the graph section height matches the StackedBarChart height (~220px) for consistent section sizing
- [x] 6.5 Add cursor affordances: grab cursor on nodes, pointer on edges

## 7. Tests

- [x] 7.1 Unit test `buildUndirectedGraph`: verify bidirectional merge, node deduplication, weight calculation
- [x] 7.2 Unit test `buildDirectedGraph`: verify separate edges preserved, direction metadata correct
- [x] 7.3 Unit test edge weight scaling: verify min/max thickness mapping
- [x] 7.4 Component test `CollaborationGraph`: renders correct number of nodes and edges for given review_matrix
- [x] 7.5 Component test: empty state renders message when review_matrix is empty
- [x] 7.6 Component test: directed toggle switches edge rendering mode
- [x] 7.7 Integration test: ProjectsPage renders graph view when toggle is set to 'graph'
