import { useEffect, useRef, useState, useCallback } from 'react'
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type Simulation,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from 'd3-force'
import type { GraphNode, GraphEdge } from '../lib/graphData'

export interface SimNode extends SimulationNodeDatum {
  id: string
  label: string
  initial: string
}

export interface SimLink extends SimulationLinkDatum<SimNode> {
  weight: number
  directed: boolean
  sourceId: string
  targetId: string
}

export interface ForceGraphState {
  nodes: SimNode[]
  links: SimLink[]
}

interface UseForceGraphOptions {
  width: number
  height: number
}

/**
 * Custom hook managing a d3-force simulation lifecycle.
 * - Initializes simulation on data change
 * - Stops on unmount
 * - Returns stable positions via tick-batched state updates
 * - Supports node dragging
 */
export function useForceGraph(
  graphNodes: GraphNode[],
  graphEdges: GraphEdge[],
  options: UseForceGraphOptions,
) {
  const { width, height } = options
  const simulationRef = useRef<Simulation<SimNode, SimLink> | null>(null)
  const [state, setState] = useState<ForceGraphState>({ nodes: [], links: [] })
  const rafRef = useRef<number>(0)

  useEffect(() => {
    // Cleanup previous simulation
    if (simulationRef.current) {
      simulationRef.current.stop()
      cancelAnimationFrame(rafRef.current)
    }

    if (graphNodes.length === 0) {
      setState({ nodes: [], links: [] })
      return
    }

    // Create simulation nodes
    const simNodes: SimNode[] = graphNodes.map((n) => ({
      id: n.id,
      label: n.label,
      initial: n.initial,
      x: undefined,
      y: undefined,
    }))

    // Create simulation links (d3-force resolves source/target by index or id)
    const simLinks: SimLink[] = graphEdges.map((e) => ({
      source: e.source,
      target: e.target,
      weight: e.weight,
      directed: e.directed,
      sourceId: e.source,
      targetId: e.target,
    }))

    const simulation = forceSimulation<SimNode>(simNodes)
      .force(
        'link',
        forceLink<SimNode, SimLink>(simLinks)
          .id((d) => d.id)
          .distance(80)
          .strength((link) => Math.min(link.weight / 10, 1)),
      )
      .force('charge', forceManyBody().strength(-200))
      .force('center', forceCenter(width / 2, height / 2))
      .force('collide', forceCollide(24))
      .alphaDecay(0.02)

    simulationRef.current = simulation

    // Batch tick updates with requestAnimationFrame
    simulation.on('tick', () => {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = requestAnimationFrame(() => {
        setState({
          nodes: [...simNodes],
          links: [...simLinks],
        })
      })
    })

    return () => {
      simulation.stop()
      cancelAnimationFrame(rafRef.current)
    }
  }, [graphNodes, graphEdges, width, height])

  // Drag handlers
  const onDragStart = useCallback((nodeId: string) => {
    const sim = simulationRef.current
    if (!sim) return
    sim.alphaTarget(0.3).restart()
    const node = sim.nodes().find((n) => n.id === nodeId)
    if (node) {
      node.fx = node.x
      node.fy = node.y
    }
  }, [])

  const onDrag = useCallback((nodeId: string, x: number, y: number) => {
    const node = simulationRef.current?.nodes().find((n) => n.id === nodeId)
    if (node) {
      node.fx = x
      node.fy = y
    }
  }, [])

  const onDragEnd = useCallback((nodeId: string) => {
    const sim = simulationRef.current
    if (!sim) return
    sim.alphaTarget(0)
    const node = sim.nodes().find((n) => n.id === nodeId)
    if (node) {
      node.fx = node.x
      node.fy = node.y
    }
  }, [])

  return {
    nodes: state.nodes,
    links: state.links,
    onDragStart,
    onDrag,
    onDragEnd,
  }
}
