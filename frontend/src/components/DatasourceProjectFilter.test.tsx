import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import DatasourceProjectFilter from './DatasourceProjectFilter'
import * as hooks from '../hooks/useMetrics'

describe('DatasourceProjectFilter', () => {
  afterEach(() => vi.restoreAllMocks())

  it('renders Launchpad bug targets and repositories separately', async () => {
    vi.spyOn(hooks, 'useProjects').mockReturnValue({
      data: {
        datasources: [{
          id: 'launchpad',
          role: 'code',
          display_name: 'Launchpad',
          projects: ['maas'],
          bug_targets: ['maas'],
          repositories: ['~maas-committers/maas/+git/maas-release-tools'],
        }],
      },
      isLoading: false,
      error: null,
    } as ReturnType<typeof hooks.useProjects>)

    render(
      <MemoryRouter>
        <DatasourceProjectFilter />
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByRole('button', { name: /All sources/ }))
    await userEvent.click(screen.getByRole('button', { name: /Launchpad/ }))

    expect(screen.getByText('Bug targets')).toBeInTheDocument()
    expect(screen.getByText('Repositories')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'maas' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '~maas-committers/maas/+git/maas-release-tools' })).toBeInTheDocument()
  })
})
