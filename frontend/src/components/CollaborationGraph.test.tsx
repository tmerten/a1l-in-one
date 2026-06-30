import { render, screen, fireEvent } from '@testing-library/react'
import { vi } from 'vitest'
import CollaborationGraph from './CollaborationGraph'

// Mock useForceGraph to avoid actual d3-force simulation in tests
vi.mock('../hooks/useForceGraph', () => ({
  useForceGraph: (nodes: Array<{ id: string; label: string; initial: string }>) => ({
    nodes: nodes.map((n, i) => ({ ...n, x: 100 + i * 50, y: 100 + i * 30 })),
    links: [],
    onDragStart: vi.fn(),
    onDrag: vi.fn(),
    onDragEnd: vi.fn(),
  }),
}))

// Mock ResizeObserver
beforeAll(() => {
  global.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
})

describe('CollaborationGraph', () => {
  it('renders correct number of nodes for given review_matrix', () => {
    const matrix = {
      alice: { bob: 3 },
      bob: { carol: 2 },
    }
    const { container } = render(
      <CollaborationGraph reviewMatrix={matrix} perPerson={undefined} />,
    )
    // 3 unique people: alice, bob, carol
    const circles = container.querySelectorAll('circle')
    expect(circles.length).toBe(3)
  })

  it('renders empty state when review_matrix is empty', () => {
    render(<CollaborationGraph reviewMatrix={{}} perPerson={undefined} />)
    expect(screen.getByText('No collaboration data for this period')).toBeInTheDocument()
  })

  it('renders empty state when review_matrix is undefined', () => {
    render(<CollaborationGraph reviewMatrix={undefined} perPerson={undefined} />)
    expect(screen.getByText('No collaboration data for this period')).toBeInTheDocument()
  })

  it('shows directed toggle buttons', () => {
    const matrix = { alice: { bob: 1 } }
    render(<CollaborationGraph reviewMatrix={matrix} perPerson={undefined} />)
    expect(screen.getByText('Undirected')).toBeInTheDocument()
    expect(screen.getByText('Directed')).toBeInTheDocument()
  })

  it('starts in undirected mode by default', () => {
    const matrix = { alice: { bob: 1 } }
    render(<CollaborationGraph reviewMatrix={matrix} perPerson={undefined} />)
    const undirectedBtn = screen.getByText('Undirected')
    expect(undirectedBtn.className).toContain('bg-blue-500')
  })

  it('switches to directed mode when toggle clicked', () => {
    const matrix = { alice: { bob: 1 } }
    render(<CollaborationGraph reviewMatrix={matrix} perPerson={undefined} />)
    const directedBtn = screen.getByText('Directed')
    fireEvent.click(directedBtn)
    expect(directedBtn.className).toContain('bg-blue-500')
  })

  it('renders node initials', () => {
    const matrix = { alice: { bob: 1 } }
    const perPerson = {
      alice: { display_name: 'Alice Johnson' },
      bob: { display_name: 'Bob Smith' },
    }
    const { container } = render(
      <CollaborationGraph reviewMatrix={matrix} perPerson={perPerson} />,
    )
    const texts = container.querySelectorAll('text')
    const initials = Array.from(texts).map((t) => t.textContent)
    expect(initials).toContain('A')
    expect(initials).toContain('B')
  })
})
