import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import WorkItemsSection from './WorkItemsSection'
import * as hooks from '../hooks/useMetrics'

function renderSection(params: Record<string, string> = {}) {
  const searchParams = new URLSearchParams(params).toString()
  const queryClient = new QueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/?${searchParams}`]}>
        <WorkItemsSection
          personId="p-1"
          from={params.from}
          to={params.to}
          sprintId={params.sprint_id}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('WorkItemsSection', () => {
  beforeEach(() => {
    vi.spyOn(hooks, 'useWorkItems').mockReturnValue({
      data: { items: [], total: 0, page: 1, per_page: 20, person_id: 'p-1', status: 'completed' },
      isLoading: false,
      error: null,
    } as ReturnType<typeof hooks.useWorkItems>)
  })

  afterEach(() => vi.restoreAllMocks())

  it('renders section header', () => {
    renderSection()
    expect(screen.getByText('Work Items')).toBeInTheDocument()
  })

  it('renders Active Work section', () => {
    renderSection()
    expect(screen.getByText(/Active Work/)).toBeInTheDocument()
  })

  it('renders Shipped section', () => {
    renderSection()
    expect(screen.getByText('Shipped Last 30 Days')).toBeInTheDocument()
  })

  it('shows loading state', () => {
    vi.spyOn(hooks, 'useWorkItems').mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as ReturnType<typeof hooks.useWorkItems>)

    renderSection()
    expect(screen.getByText('Work Items')).toBeInTheDocument()
  })

  it('displays work items when loaded', () => {
    vi.spyOn(hooks, 'useWorkItems').mockReturnValue({
      data: {
        items: [{
          id: '1',
          datasource: 'github',
          event_type: 'pull_request',
          external_id: '42',
          project: 'owner/repo',
          title: 'Fix the bug',
          status: 'merged',
          timestamp: '2026-06-15T10:00:00Z',
          url: 'https://github.com/owner/repo/pull/42',
        }],
        total: 1,
        page: 1,
        per_page: 20,
        person_id: 'p-1',
        status: 'completed',
      },
      isLoading: false,
      error: null,
    } as ReturnType<typeof hooks.useWorkItems>)

    renderSection()
    expect(screen.getAllByText('Fix the bug')[0]).toBeInTheDocument()
  })

  it('shows grouped view by default', () => {
    renderSection()
    expect(screen.getByRole('button', { name: 'Grouped' })).toBeInTheDocument()
  })
})
