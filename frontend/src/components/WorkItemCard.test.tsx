import { render, screen } from '@testing-library/react'
import WorkItemCard from './WorkItemCard'

const defaultItem = {
  id: '1',
  datasource: 'github',
  event_type: 'pull_request',
  external_id: '42',
  project: 'owner/repo',
  title: 'Fix the authentication bug',
  status: 'merged',
  timestamp: '2026-06-15T10:00:00Z',
  url: 'https://github.com/owner/repo/pull/42',
}

describe('WorkItemCard', () => {
  it('renders title', () => {
    render(<WorkItemCard item={defaultItem} />)
    expect(screen.getByText('Fix the authentication bug')).toBeInTheDocument()
  })

  it('renders datasource badge for GitHub', () => {
    render(<WorkItemCard item={defaultItem} />)
    expect(screen.getByText('GH')).toBeInTheDocument()
  })

  it('renders datasource badge for Jira', () => {
    render(<WorkItemCard item={{ ...defaultItem, datasource: 'jira' }} />)
    expect(screen.getByText('Jira')).toBeInTheDocument()
  })

  it('renders status badge', () => {
    render(<WorkItemCard item={defaultItem} />)
    expect(screen.getByText('merged')).toBeInTheDocument()
  })

  it('renders external link', () => {
    render(<WorkItemCard item={defaultItem} />)
    const link = screen.getByRole('link', { name: /Open/ })
    expect(link).toHaveAttribute('href', 'https://github.com/owner/repo/pull/42')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('renders metadata chips for PR', () => {
    render(<WorkItemCard item={{
      ...defaultItem,
      metadata: { additions: 100, deletions: 50, reviewers: ['alice', 'bob'] },
    }} />)
    expect(screen.getByText(/\+100 -50/)).toBeInTheDocument()
  })

  it('renders metadata for Jira issue', () => {
    render(<WorkItemCard item={{
      ...defaultItem,
      datasource: 'jira',
      event_type: 'issue',
      metadata: { issue_type: 'Feature', story_points: 5 },
    }} />)
    expect(screen.getByText(/5 pts/)).toBeInTheDocument()
  })

  it('renders in compact mode with reduced layout', () => {
    render(<WorkItemCard item={defaultItem} compact />)
    expect(screen.getByText('Fix the authentication bug')).toBeInTheDocument()
  })

  it('shows draft status badge', () => {
    render(<WorkItemCard item={{ ...defaultItem, status: 'draft' }} />)
    expect(screen.getByText('draft')).toBeInTheDocument()
  })

  it('shows open status badge', () => {
    render(<WorkItemCard item={{ ...defaultItem, status: 'open' }} />)
    expect(screen.getByText('open')).toBeInTheDocument()
  })

  it('renders commit with clickable SHA link', () => {
    render(<WorkItemCard item={{
      ...defaultItem,
      event_type: 'commit',
      external_id: 'abc123def456789',
      metadata: { sha: 'abc123d' },
      url: 'https://github.com/owner/repo/commit/abc123def456789',
    }} />)
    const link = screen.getByRole('link', { name: /Commit abc123d/ })
    expect(link).toHaveAttribute('href', 'https://github.com/owner/repo/commit/abc123def456789')
  })

  it('renders review with clickable review ID link', () => {
    render(<WorkItemCard item={{
      ...defaultItem,
      event_type: 'pull_request_review',
      external_id: '12345',
      metadata: { pr_number: 42 },
      url: 'https://github.com/owner/repo/pull/42#pullrequestreview-12345',
    }} />)
    const link = screen.getByRole('link', { name: /Review 12345/ })
    expect(link).toHaveAttribute('href', 'https://github.com/owner/repo/pull/42#pullrequestreview-12345')
  })

  it('renders commit with PR link', () => {
    render(<WorkItemCard item={{
      ...defaultItem,
      event_type: 'commit',
      external_id: 'abc123def456789',
      metadata: { sha: 'abc123d', pr_number: 42 },
      url: 'https://github.com/owner/repo/commit/abc123def456789',
    }} />)
    const prLink = screen.getByRole('link', { name: /PR #42/ })
    expect(prLink).toHaveAttribute('href', 'https://github.com/owner/repo/pull/42')
  })

  it('renders Launchpad merge proposal as MP', () => {
    render(<WorkItemCard item={{
      ...defaultItem,
      datasource: 'launchpad',
      event_type: 'pull_request',
      external_id: '505857',
      project: '~maas-committers/maas/+git/maas',
      title: 'feat: add FIPS compliance',
      url: 'https://code.launchpad.net/~example/maas/+git/maas/+merge/505857',
    }} />)

    expect(screen.getByText('LP')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /MP 505857/ })).toHaveAttribute(
      'href',
      'https://code.launchpad.net/~example/maas/+git/maas/+merge/505857',
    )
  })
})
