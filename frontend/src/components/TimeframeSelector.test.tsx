import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, useSearchParams } from 'react-router-dom'
import { vi } from 'vitest'
import TimeframeSelector from './TimeframeSelector'
import * as hooks from '../hooks/useMetrics'

const SPRINTS = [
  { id: 'sprint-1', name: 'Sprint 1', is_active: true, start_date: '2024-01-01T00:00:00Z', end_date: '2024-01-14T00:00:00Z' },
  { id: 'sprint-2', name: 'Sprint 2', is_active: false, start_date: '2023-12-01T00:00:00Z', end_date: '2023-12-15T00:00:00Z' },
]

function mockSprints(sprints: typeof SPRINTS | null = SPRINTS) {
  vi.spyOn(hooks, 'useSprints').mockReturnValue({
    data: sprints,
    isLoading: false,
    error: null,
  } as ReturnType<typeof hooks.useSprints>)
}

function renderWith(initialSearch: string) {
  function Probe() {
    const [params] = useSearchParams()
    return (
      <>
        <TimeframeSelector />
        <div data-testid="params">{params.toString()}</div>
      </>
    )
  }
  return render(
    <MemoryRouter initialEntries={[`/?${initialSearch}`]}>
      <Probe />
    </MemoryRouter>,
  )
}

describe('TimeframeSelector — always-visible date picker', () => {
  afterEach(() => vi.restoreAllMocks())

  it('shows date inputs when a preset is selected', () => {
    mockSprints()
    renderWith('from=2024-01-01&to=2024-01-31')
    const fromInput = screen.getByDisplayValue('2024-01-01')
    const toInput = screen.getByDisplayValue('2024-01-31')
    expect(fromInput).toBeInTheDocument()
    expect(toInput).toBeInTheDocument()
    expect(fromInput).toHaveAttribute('type', 'date')
    expect(toInput).toHaveAttribute('type', 'date')
  })

  it('shows date inputs with sprint start/end dates when a sprint is selected', () => {
    mockSprints()
    renderWith('sprint_id=sprint-1')
    expect(screen.getByDisplayValue('2024-01-01')).toBeInTheDocument()
    expect(screen.getByDisplayValue('2024-01-14')).toBeInTheDocument()
  })

  it('keeps date inputs visible when only a sprint param is present (no from/to in URL)', () => {
    mockSprints()
    renderWith('sprint_id=sprint-1')
    const inputs = screen.getAllByDisplayValue(/2024-01-/)
    expect(inputs.length).toBe(2)
  })

  it('shows the Custom option before any manual date edit', () => {
    mockSprints()
    renderWith('')
    expect(screen.getByText('Custom range')).toBeInTheDocument()
  })

  it('switches to custom mode and clears sprint_id when the to-date is edited', () => {
    mockSprints()
    const { container } = renderWith('sprint_id=sprint-1')
    const dateInputs = container.querySelectorAll('input[type="date"]')
    const toInput = dateInputs[1] as HTMLInputElement
    fireEvent.change(toInput, { target: { value: '2024-01-20' } })
    const params = screen.getByTestId('params').textContent || ''
    expect(params).toContain('from=2024-01-01')
    expect(params).toContain('to=2024-01-20')
    expect(params).not.toContain('sprint_id')
    const select = screen.getByRole('combobox') as HTMLSelectElement
    expect(select.value).toBe('custom')
  })

  it('switches to custom mode and clears sprint_id when the from-date is edited', () => {
    mockSprints()
    const { container } = renderWith('sprint_id=sprint-1')
    const dateInputs = container.querySelectorAll('input[type="date"]')
    const fromInput = dateInputs[0] as HTMLInputElement
    fireEvent.change(fromInput, { target: { value: '2023-12-25' } })
    const params = screen.getByTestId('params').textContent || ''
    expect(params).toContain('from=2023-12-25')
    expect(params).toContain('to=2024-01-14')
    expect(params).not.toContain('sprint_id')
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('custom')
  })

  it('selecting Custom from the dropdown while a preset is active keeps the current range', () => {
    mockSprints()
    renderWith('from=2024-01-01&to=2024-01-31')
    const select = screen.getByRole('combobox') as HTMLSelectElement
    fireEvent.change(select, { target: { value: 'custom' } })
    expect(screen.getByDisplayValue('2024-01-01')).toBeInTheDocument()
    expect(screen.getByDisplayValue('2024-01-31')).toBeInTheDocument()
  })

  it('editing a date input while a preset is active switches dropdown to Custom', () => {
    mockSprints()
    const { container } = renderWith('from=2024-01-01&to=2024-01-31')
    const dateInputs = container.querySelectorAll('input[type="date"]')
    fireEvent.change(dateInputs[0] as HTMLInputElement, { target: { value: '2024-01-05' } })
    expect((screen.getByRole('combobox') as HTMLSelectElement).value).toBe('custom')
  })
})
