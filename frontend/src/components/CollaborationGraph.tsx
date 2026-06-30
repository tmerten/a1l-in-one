import { useState, useRef, useMemo, useCallback, useEffect } from 'react'
import {
  buildUndirectedGraph,
  buildDirectedGraph,
  computeEdgeThickness,
  getWeightRange,
} from '../lib/graphData'
import { useForceGraph, type SimNode, type SimLink } from '../hooks/useForceGraph'

type ReviewMatrix = { [reviewer: string]: { [author: string]: number } }
type PerPerson = { [actor: string]: { [key: string]: unknown } }

interface CollaborationGraphProps {
  reviewMatrix: ReviewMatrix | undefined
  perPerson: PerPerson | undefined
}

const GRAPH_HEIGHT = 220
const NODE_RADIUS = 18

export default function CollaborationGraph({ reviewMatrix, perPerson }: CollaborationGraphProps) {
  const [directed, setDirected] = useState(false)
  const [tooltip, setTooltip] = useState<{ x: number; y: number; text: string } | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(400)

  // Responsive width
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setWidth(entry.contentRect.width)
      }
    })
    observer.observe(el)
    setWidth(el.clientWidth)
    return () => observer.disconnect()
  }, [])

  // Build graph data
  const graphData = useMemo(() => {
    if (!reviewMatrix || Object.keys(reviewMatrix).length === 0) {
      return { nodes: [], edges: [] }
    }
    return directed
      ? buildDirectedGraph(reviewMatrix, perPerson)
      : buildUndirectedGraph(reviewMatrix, perPerson)
  }, [reviewMatrix, perPerson, directed])

  // Force simulation
  const { nodes, links, onDragStart, onDrag, onDragEnd } = useForceGraph(
    graphData.nodes,
    graphData.edges,
    { width, height: GRAPH_HEIGHT },
  )

  const weightRange = useMemo(() => getWeightRange(graphData.edges), [graphData.edges])

  // Drag state
  const draggingRef = useRef<string | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  const getSvgPoint = useCallback((e: React.MouseEvent) => {
    const svg = svgRef.current
    if (!svg) return { x: 0, y: 0 }
    const rect = svg.getBoundingClientRect()
    return { x: e.clientX - rect.left, y: e.clientY - rect.top }
  }, [])

  const handleMouseDown = useCallback((e: React.MouseEvent, nodeId: string) => {
    e.preventDefault()
    draggingRef.current = nodeId
    onDragStart(nodeId)
  }, [onDragStart])

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!draggingRef.current) return
    const pt = getSvgPoint(e)
    onDrag(draggingRef.current, pt.x, pt.y)
  }, [onDrag, getSvgPoint])

  const handleMouseUp = useCallback(() => {
    if (draggingRef.current) {
      onDragEnd(draggingRef.current)
      draggingRef.current = null
    }
  }, [onDragEnd])

  // Tooltip handlers
  const showNodeTooltip = useCallback((e: React.MouseEvent, node: SimNode) => {
    const pt = getSvgPoint(e)
    setTooltip({ x: pt.x, y: pt.y - 30, text: node.label })
  }, [getSvgPoint])

  const showEdgeTooltip = useCallback((e: React.MouseEvent, link: SimLink) => {
    const pt = getSvgPoint(e)
    const label = link.directed
      ? `${link.sourceId} → ${link.targetId}: ${link.weight}`
      : `${link.weight} reviews`
    setTooltip({ x: pt.x, y: pt.y - 20, text: label })
  }, [getSvgPoint])

  const hideTooltip = useCallback(() => setTooltip(null), [])

  // Empty state
  if (!reviewMatrix || Object.keys(reviewMatrix).length === 0) {
    return (
      <div className="flex items-center justify-center h-[220px] text-sm text-gray-500">
        No collaboration data for this period
      </div>
    )
  }

  return (
    <div ref={containerRef} className="relative">
      {/* Directed/Undirected toggle */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs text-gray-500">Mode:</span>
        <button
          onClick={() => setDirected(false)}
          className={`px-2 py-0.5 text-xs rounded-l-full border ${
            !directed
              ? 'bg-blue-500 text-white border-blue-500'
              : 'bg-white text-gray-600 border-gray-300'
          }`}
        >
          Undirected
        </button>
        <button
          onClick={() => setDirected(true)}
          className={`px-2 py-0.5 text-xs rounded-r-full border -ml-2 ${
            directed
              ? 'bg-blue-500 text-white border-blue-500'
              : 'bg-white text-gray-600 border-gray-300'
          }`}
        >
          Directed
        </button>
      </div>

      {/* SVG Graph */}
      <svg
        ref={svgRef}
        width={width}
        height={GRAPH_HEIGHT}
        className="border border-gray-200 rounded-md bg-gray-50"
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => { handleMouseUp(); hideTooltip() }}
      >
        {/* Arrow marker for directed edges */}
        {directed && (
          <defs>
            <marker
              id="arrowhead"
              viewBox="0 0 10 10"
              refX={10 + NODE_RADIUS * 0.6}
              refY={5}
              markerWidth={6}
              markerHeight={6}
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b82f6" />
            </marker>
          </defs>
        )}

        {/* Edges */}
        {links.map((link, i) => {
          const source = link.source as SimNode
          const target = link.target as SimNode
          if (!source.x || !source.y || !target.x || !target.y) return null

          const thickness = computeEdgeThickness(link.weight, weightRange.min, weightRange.max)

          if (directed) {
            // Check if there's a reverse edge (for arc offset)
            const hasReverse = links.some(
              (l) => (l.source as SimNode).id === target.id && (l.target as SimNode).id === source.id
            )

            if (hasReverse) {
              // Offset with a quadratic curve
              const dx = target.x - source.x
              const dy = target.y - source.y
              const cx = (source.x + target.x) / 2 - dy * 0.15
              const cy = (source.y + target.y) / 2 + dx * 0.15

              return (
                <path
                  key={`edge-${i}`}
                  d={`M ${source.x} ${source.y} Q ${cx} ${cy} ${target.x} ${target.y}`}
                  fill="none"
                  stroke="#3b82f6"
                  strokeWidth={thickness}
                  strokeOpacity={0.6}
                  markerEnd="url(#arrowhead)"
                  className="cursor-pointer"
                  onMouseEnter={(e) => showEdgeTooltip(e, link)}
                  onMouseLeave={hideTooltip}
                />
              )
            }

            return (
              <line
                key={`edge-${i}`}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                stroke="#3b82f6"
                strokeWidth={thickness}
                strokeOpacity={0.6}
                markerEnd="url(#arrowhead)"
                className="cursor-pointer"
                onMouseEnter={(e) => showEdgeTooltip(e, link)}
                onMouseLeave={hideTooltip}
              />
            )
          }

          // Undirected: simple line
          return (
            <line
              key={`edge-${i}`}
              x1={source.x}
              y1={source.y}
              x2={target.x}
              y2={target.y}
              stroke="#9ca3af"
              strokeWidth={thickness}
              strokeOpacity={0.7}
              className="cursor-pointer"
              onMouseEnter={(e) => showEdgeTooltip(e, link)}
              onMouseLeave={hideTooltip}
            />
          )
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          if (!node.x || !node.y) return null
          return (
            <g
              key={node.id}
              transform={`translate(${node.x}, ${node.y})`}
              className="cursor-grab active:cursor-grabbing"
              onMouseDown={(e) => handleMouseDown(e, node.id)}
              onMouseEnter={(e) => showNodeTooltip(e, node)}
              onMouseLeave={hideTooltip}
            >
              <circle
                r={NODE_RADIUS}
                fill="#3b82f6"
                stroke="#fff"
                strokeWidth={2}
                className="drop-shadow-sm hover:stroke-blue-300 hover:stroke-[3px]"
              />
              <text
                textAnchor="middle"
                dominantBaseline="central"
                fill="white"
                fontSize={12}
                fontWeight={600}
                className="pointer-events-none select-none"
              >
                {node.initial}
              </text>
            </g>
          )
        })}
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute px-2 py-1 text-xs text-white bg-gray-800 rounded shadow pointer-events-none whitespace-nowrap"
          style={{ left: tooltip.x, top: tooltip.y, transform: 'translate(-50%, -100%)' }}
        >
          {tooltip.text}
        </div>
      )}
    </div>
  )
}
