import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import PersonDetailPage from './PersonDetailPage'
import * as hooks from '../hooks/useMetrics'

const EMPTY_TS = { data: { bucket_size: 'day', data: [] }, isLoading: false }

function renderPage(personId = 'p-1') {
  return render(
    <MemoryRouter initialEntries={[`/persons/${personId}`]}>
      <Routes>
        <Route path="/persons/:personId" element={<PersonDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('PersonDetailPage', () => {
  beforeEach(() => {
    vi.spyOn(hooks, 'useContributionVolumeTs').mockReturnValue(EMPTY_TS as ReturnType<typeof hooks.useContributionVolumeTs>)
    vi.spyOn(hooks, 'useVelocityTs').mockReturnValue(EMPTY_TS as ReturnType<typeof hooks.useVelocityTs>)
    vi.spyOn(hooks, 'useCollaborationTs').mockReturnValue(EMPTY_TS as ReturnType<typeof hooks.useCollaborationTs>)
  })

  afterEach(() => vi.restoreAllMocks())

  it('shows loading state while fetching', () => {
    vi.spyOn(hooks, 'usePersonContributions').mockReturnValue({
      data: undefined, isLoading: true, error: null,
    } as ReturnType<typeof hooks.usePersonContributions>)
    renderPage()
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('renders person name and back link', () => {
    vi.spyOn(hooks, 'usePersonContributions').mockReturnValue({
      data: {
        display_name: 'Alice Johnson',
        identities: [{ source: 'github', external_id: 'alicejohnson' }],
        contributions: [],
      },
      isLoading: false, error: null,
    } as ReturnType<typeof hooks.usePersonContributions>)
    renderPage()
    expect(screen.getByText('Alice Johnson')).toBeInTheDocument()
    expect(screen.getByText('← People')).toBeInTheDocument()
  })

  it('renders charts when GitHub identity is present', () => {
    vi.spyOn(hooks, 'usePersonContributions').mockReturnValue({
      data: {
        display_name: 'Alice Johnson',
        identities: [{ source: 'github', external_id: 'alicejohnson' }],
        contributions: [],
      },
      isLoading: false, error: null,
    } as ReturnType<typeof hooks.usePersonContributions>)
    renderPage()
    expect(screen.getByText('Contribution Volume over time')).toBeInTheDocument()
    expect(screen.getByText('Velocity over time')).toBeInTheDocument()
    expect(screen.getByText('Collaboration over time')).toBeInTheDocument()
  })

  it('shows fallback message when no GitHub identity', () => {
    vi.spyOn(hooks, 'usePersonContributions').mockReturnValue({
      data: {
        display_name: 'Bob (Jira only)',
        identities: [{ source: 'jira', external_id: '557058:abc' }],
        contributions: [],
      },
      isLoading: false, error: null,
    } as ReturnType<typeof hooks.usePersonContributions>)
    renderPage()
    expect(screen.getByText(/Chart data not available/)).toBeInTheDocument()
    expect(screen.queryByText('Contribution Volume over time')).not.toBeInTheDocument()
  })
})
