import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import ProjectsPage from './ProjectsPage'
import * as hooks from '../hooks/useMetrics'

// Mock ResizeObserver
beforeAll(() => {
  global.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
})

// Mock settings
vi.mock('../components/SettingsPanel', async () => {
  const actual = await vi.importActual<typeof import('../components/SettingsPanel')>('../components/SettingsPanel')
  return {
    ...actual,
    useSettings: () => ({
      settings: {
        sections: { volume: false, velocity: false, composition: false, collaboration: true },
        outliers: false,
      },
    }),
    default: () => null,
  }
})

// Mock useForceGraph
vi.mock('../hooks/useForceGraph', () => ({
  useForceGraph: (nodes: Array<{ id: string; label: string; initial: string }>) => ({
    nodes: nodes.map((n, i) => ({ ...n, x: 100 + i * 50, y: 100 + i * 30 })),
    links: [],
    onDragStart: vi.fn(),
    onDrag: vi.fn(),
    onDragEnd: vi.fn(),
  }),
}))

const COLLAB_DATA = {
  review_matrix: { alice: { bob: 3 }, bob: { alice: 2 } },
  per_person: { alice: { display_name: 'Alice' }, bob: { display_name: 'Bob' } },
}

describe('ProjectsPage graph view integration', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders graph view when toggle is set to graph', () => {
    vi.spyOn(hooks, 'useCollaboration').mockReturnValue({
      data: COLLAB_DATA, isLoading: false, error: null,
    } as unknown as ReturnType<typeof hooks.useCollaboration>)
    vi.spyOn(hooks, 'useCollaborationTs').mockReturnValue({
      data: null, isLoading: false, error: null,
    } as unknown as ReturnType<typeof hooks.useCollaborationTs>)
    vi.spyOn(hooks, 'useContributionVolume').mockReturnValue({
      data: null, isLoading: false, error: null,
    } as unknown as ReturnType<typeof hooks.useContributionVolume>)
    vi.spyOn(hooks, 'useVelocity').mockReturnValue({
      data: null, isLoading: false, error: null,
    } as unknown as ReturnType<typeof hooks.useVelocity>)
    vi.spyOn(hooks, 'useComposition').mockReturnValue({
      data: null, isLoading: false, error: null,
    } as unknown as ReturnType<typeof hooks.useComposition>)
    vi.spyOn(hooks, 'useSprintBurndown').mockReturnValue({
      data: null, isLoading: false, error: null,
    } as unknown as ReturnType<typeof hooks.useSprintBurndown>)
    vi.spyOn(hooks, 'useContributionVolumeTs').mockReturnValue({
      data: null, isLoading: false, error: null,
    } as unknown as ReturnType<typeof hooks.useContributionVolumeTs>)
    vi.spyOn(hooks, 'useVelocityTs').mockReturnValue({
      data: null, isLoading: false, error: null,
    } as unknown as ReturnType<typeof hooks.useVelocityTs>)

    render(
      <MemoryRouter initialEntries={['/projects']}>
        <ProjectsPage />
      </MemoryRouter>,
    )

    // Click the "graph" toggle
    const graphButton = screen.getByText('graph')
    fireEvent.click(graphButton)

    // Should now show the CollaborationGraph directed/undirected toggle
    expect(screen.getByText('Undirected')).toBeInTheDocument()
    expect(screen.getByText('Directed')).toBeInTheDocument()
  })
})
