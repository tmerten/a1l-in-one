import { render, screen, fireEvent } from '@testing-library/react'
import ChartSectionToggle from './ChartSectionToggle'

describe('ChartSectionToggle', () => {
  it('renders Cards and Charts buttons', () => {
    render(<ChartSectionToggle value="cards" onChange={() => {}} />)
    expect(screen.getByText('cards')).toBeInTheDocument()
    expect(screen.getByText('charts')).toBeInTheDocument()
  })

  it('calls onChange with "charts" when Charts is clicked', () => {
    const onChange = vi.fn()
    render(<ChartSectionToggle value="cards" onChange={onChange} />)
    fireEvent.click(screen.getByText('charts'))
    expect(onChange).toHaveBeenCalledWith('charts')
  })

  it('calls onChange with "cards" when Cards is clicked', () => {
    const onChange = vi.fn()
    render(<ChartSectionToggle value="charts" onChange={onChange} />)
    fireEvent.click(screen.getByText('cards'))
    expect(onChange).toHaveBeenCalledWith('cards')
  })

  it('highlights the active option', () => {
    render(<ChartSectionToggle value="charts" onChange={() => {}} />)
    const chartsBtn = screen.getByText('charts')
    expect(chartsBtn.className).toContain('bg-gray-900')
    const cardsBtn = screen.getByText('cards')
    expect(cardsBtn.className).toContain('bg-white')
  })
})
