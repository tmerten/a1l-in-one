import { describe, it, expect } from 'vitest'
import {
  buildUndirectedGraph,
  buildDirectedGraph,
  computeEdgeThickness,
  getWeightRange,
} from './graphData'

describe('buildUndirectedGraph', () => {
  it('merges bidirectional pairs into a single edge with summed weight', () => {
    const matrix = {
      alice: { bob: 3 },
      bob: { alice: 2 },
    }
    const result = buildUndirectedGraph(matrix)

    expect(result.nodes).toHaveLength(2)
    expect(result.edges).toHaveLength(1)
    expect(result.edges[0].weight).toBe(5)
    expect(result.edges[0].directed).toBe(false)
  })

  it('deduplicates nodes from reviewer and author keys', () => {
    const matrix = {
      alice: { bob: 1, carol: 2 },
      bob: { carol: 1 },
    }
    const result = buildUndirectedGraph(matrix)

    const nodeIds = result.nodes.map((n) => n.id).sort()
    expect(nodeIds).toEqual(['alice', 'bob', 'carol'])
  })

  it('includes persons who appear only as authors', () => {
    const matrix = {
      alice: { bob: 5 },
    }
    const result = buildUndirectedGraph(matrix)

    const nodeIds = result.nodes.map((n) => n.id).sort()
    expect(nodeIds).toEqual(['alice', 'bob'])
  })

  it('uses display_name from perPerson for labels', () => {
    const matrix = { alice: { bob: 1 } }
    const perPerson = {
      alice: { display_name: 'Alice Johnson' },
      bob: { display_name: 'Bob Smith' },
    }
    const result = buildUndirectedGraph(matrix, perPerson)

    const alice = result.nodes.find((n) => n.id === 'alice')!
    expect(alice.label).toBe('Alice Johnson')
    expect(alice.initial).toBe('A')
  })

  it('falls back to actor ID when display_name is missing', () => {
    const matrix = { alice: { bob: 1 } }
    const result = buildUndirectedGraph(matrix)

    const alice = result.nodes.find((n) => n.id === 'alice')!
    expect(alice.label).toBe('alice')
    expect(alice.initial).toBe('A')
  })

  it('returns empty graph for empty matrix', () => {
    const result = buildUndirectedGraph({})
    expect(result.nodes).toHaveLength(0)
    expect(result.edges).toHaveLength(0)
  })
})

describe('buildDirectedGraph', () => {
  it('keeps separate edges for each direction', () => {
    const matrix = {
      alice: { bob: 3 },
      bob: { alice: 2 },
    }
    const result = buildDirectedGraph(matrix)

    expect(result.nodes).toHaveLength(2)
    expect(result.edges).toHaveLength(2)

    const aliceToBob = result.edges.find((e) => e.source === 'alice' && e.target === 'bob')!
    expect(aliceToBob.weight).toBe(3)
    expect(aliceToBob.directed).toBe(true)

    const bobToAlice = result.edges.find((e) => e.source === 'bob' && e.target === 'alice')!
    expect(bobToAlice.weight).toBe(2)
  })

  it('excludes self-referential edges', () => {
    const matrix = {
      alice: { alice: 1, bob: 2 },
    }
    const result = buildDirectedGraph(matrix)

    expect(result.edges).toHaveLength(1)
    expect(result.edges[0].source).toBe('alice')
    expect(result.edges[0].target).toBe('bob')
  })

  it('preserves direction metadata on all edges', () => {
    const matrix = { alice: { bob: 1 } }
    const result = buildDirectedGraph(matrix)

    expect(result.edges[0].directed).toBe(true)
  })
})

describe('computeEdgeThickness', () => {
  it('returns 1px for minimum weight', () => {
    expect(computeEdgeThickness(1, 1, 10)).toBe(1)
  })

  it('returns 6px for maximum weight', () => {
    expect(computeEdgeThickness(10, 1, 10)).toBe(6)
  })

  it('returns middle value for midpoint weight', () => {
    const thickness = computeEdgeThickness(5, 0, 10)
    expect(thickness).toBe(3.5)
  })

  it('returns 3px when all weights are equal', () => {
    expect(computeEdgeThickness(5, 5, 5)).toBe(3)
  })
})

describe('getWeightRange', () => {
  it('returns correct min and max', () => {
    const edges = [
      { source: 'a', target: 'b', weight: 3, directed: false },
      { source: 'b', target: 'c', weight: 7, directed: false },
      { source: 'a', target: 'c', weight: 1, directed: false },
    ]
    const range = getWeightRange(edges)
    expect(range.min).toBe(1)
    expect(range.max).toBe(7)
  })

  it('returns 0/0 for empty edges', () => {
    const range = getWeightRange([])
    expect(range.min).toBe(0)
    expect(range.max).toBe(0)
  })
})
