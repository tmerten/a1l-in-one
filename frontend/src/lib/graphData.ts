/**
 * Transforms the review_matrix from the collaboration API into graph data
 * structures suitable for force-directed visualization.
 */

export interface GraphNode {
  id: string
  label: string // display name or fallback to actor ID
  initial: string // first character of label
}

export interface GraphEdge {
  source: string // node id
  target: string // node id
  weight: number
  directed: boolean
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

type ReviewMatrix = { [reviewer: string]: { [author: string]: number } }
type PerPerson = { [actor: string]: { [key: string]: unknown } }

/**
 * Build an undirected graph from the review matrix.
 * Bidirectional pairs are merged: A->B: 3 + B->A: 2 becomes edge(A, B, weight=5).
 * Nodes are deduplicated from all reviewer and author keys.
 */
export function buildUndirectedGraph(
  matrix: ReviewMatrix,
  perPerson?: PerPerson,
): GraphData {
  const nodeSet = new Set<string>()
  const edgeMap = new Map<string, number>()

  for (const [reviewer, authors] of Object.entries(matrix)) {
    nodeSet.add(reviewer)
    for (const [author, count] of Object.entries(authors)) {
      nodeSet.add(author)
      // Canonical key: sorted pair to merge bidirectional
      const key = [reviewer, author].sort().join('::')
      edgeMap.set(key, (edgeMap.get(key) ?? 0) + count)
    }
  }

  const nodes = buildNodes(nodeSet, perPerson)
  const edges: GraphEdge[] = []

  for (const [key, weight] of edgeMap.entries()) {
    const [source, target] = key.split('::')
    edges.push({ source, target, weight, directed: false })
  }

  return { nodes, edges }
}

/**
 * Build a directed graph from the review matrix.
 * Each direction is kept as a separate edge: A->B: 3 and B->A: 2 are two edges.
 * Self-referential edges (reviewer === author) are excluded.
 */
export function buildDirectedGraph(
  matrix: ReviewMatrix,
  perPerson?: PerPerson,
): GraphData {
  const nodeSet = new Set<string>()
  const edges: GraphEdge[] = []

  for (const [reviewer, authors] of Object.entries(matrix)) {
    nodeSet.add(reviewer)
    for (const [author, count] of Object.entries(authors)) {
      if (reviewer === author) continue // exclude self-reviews
      nodeSet.add(author)
      edges.push({ source: reviewer, target: author, weight: count, directed: true })
    }
  }

  const nodes = buildNodes(nodeSet, perPerson)
  return { nodes, edges }
}

/**
 * Compute stroke width for an edge given min/max weights in the graph.
 * Maps linearly from 1px (min weight) to 6px (max weight).
 */
export function computeEdgeThickness(
  weight: number,
  minWeight: number,
  maxWeight: number,
): number {
  if (minWeight === maxWeight) return 3 // uniform weight: use middle thickness
  const ratio = (weight - minWeight) / (maxWeight - minWeight)
  return 1 + ratio * 5 // 1px to 6px
}

/**
 * Get min and max edge weights from a set of edges.
 */
export function getWeightRange(edges: GraphEdge[]): { min: number; max: number } {
  if (edges.length === 0) return { min: 0, max: 0 }
  let min = Infinity
  let max = -Infinity
  for (const edge of edges) {
    if (edge.weight < min) min = edge.weight
    if (edge.weight > max) max = edge.weight
  }
  return { min, max }
}

function buildNodes(nodeSet: Set<string>, perPerson?: PerPerson): GraphNode[] {
  return Array.from(nodeSet).map((id) => {
    const displayName = perPerson?.[id]?.display_name as string | undefined
    const label = displayName || id
    const initial = label.charAt(0).toUpperCase()
    return { id, label, initial }
  })
}
