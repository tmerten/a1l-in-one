import { render, screen, fireEvent } from '@testing-library/react'
import StackedBarChart from './StackedBarChart'

const DATA = [
  { bucket: '2026-06-01', commits: 5, prs: 2, issues: 1 },
  { bucket: '2026-06-02', commits: 3, prs: 1, issues: 0 },
]

const SERIES = [
  { key: 'commits', label: 'Commits', color: '#6366f1', visible: true },
  { key: 'prs', label: 'PRs', color: '#10b981', visible: true },
  { key: 'issues', label: 'Issues', color: '#f59e0b', visible: true },
]

describe('StackedBarChart', () => {
  it('shows empty state when no data', () => {
    render(<StackedBarChart data={[]} series={SERIES} onToggle={() => {}} bucketSize="day" />)
    expect(screen.getByText('No data for this timeframe')).toBeInTheDocument()
  })

  it('renders a legend button for each series', () => {
    render(<StackedBarChart data={DATA} series={SERIES} onToggle={() => {}} bucketSize="day" />)
    expect(screen.getByText('Commits')).toBeInTheDocument()
    expect(screen.getByText('PRs')).toBeInTheDocument()
    expect(screen.getByText('Issues')).toBeInTheDocument()
  })

  it('applies reduced opacity to hidden series legend button', () => {
    const seriesWithHidden = SERIES.map(s =>
      s.key === 'prs' ? { ...s, visible: false } : s,
    )
    render(<StackedBarChart data={DATA} series={seriesWithHidden} onToggle={() => {}} bucketSize="day" />)
    const prsButton = screen.getByText('PRs').closest('button')!
    expect(prsButton.className).toContain('opacity-40')
  })

  it('calls onToggle with the correct key when legend button clicked', () => {
    const onToggle = vi.fn()
    render(<StackedBarChart data={DATA} series={SERIES} onToggle={onToggle} bucketSize="day" />)
    fireEvent.click(screen.getByText('Commits').closest('button')!)
    expect(onToggle).toHaveBeenCalledWith('commits')
  })
})
