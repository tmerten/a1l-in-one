import { useState } from 'react'
import WorkItemCard from './WorkItemCard'
import CommitList from './CommitList'
import type { components } from '../api/types'

type WorkItem = components['schemas']['WorkItem']

interface GroupedWorkItemsViewProps {
  items: WorkItem[]
  personId: string
  from?: string
  to?: string
}

function CollapsibleSection({ title, count, children, defaultOpen = true }: {
  title: string
  count: number
  children: React.ReactNode
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)

  if (count === 0) return null

  return (
    <div className="mb-4">
      <button
        className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2"
        onClick={() => setOpen(!open)}
      >
        <span className="text-gray-400">{open ? '▾' : '▸'}</span>
        {title} ({count})
      </button>
      {open && <div className="space-y-2">{children}</div>}
    </div>
  )
}

export default function GroupedWorkItemsView({ items, personId, from, to }: GroupedWorkItemsViewProps) {
  const jiraIssues = items.filter(i => i.datasource === 'jira' && i.event_type === 'issue')
  const pullRequests = items.filter(i => i.event_type === 'pull_request')
  const reviews = items.filter(i => i.event_type === 'pull_request_review')
  const githubIssues = items.filter(i => i.datasource === 'github' && i.event_type === 'issue')
  const commitCount = items.filter(i => i.event_type === 'commit').length
  const prCount = pullRequests.length

  return (
    <div className="space-y-4">
      <CollapsibleSection title="Jira Issues" count={jiraIssues.length}>
        {jiraIssues.map(item => (
          <WorkItemCard key={item.id} item={item} />
        ))}
      </CollapsibleSection>

      <CollapsibleSection title="Pull Requests" count={pullRequests.length}>
        {pullRequests.map(item => (
          <WorkItemCard key={item.id} item={item} />
        ))}
      </CollapsibleSection>

      <CollapsibleSection title="Reviews" count={reviews.length}>
        {reviews.map(item => (
          <WorkItemCard key={item.id} item={item} />
        ))}
      </CollapsibleSection>

      <CollapsibleSection title="GitHub Issues" count={githubIssues.length}>
        {githubIssues.map(item => (
          <WorkItemCard key={item.id} item={item} />
        ))}
      </CollapsibleSection>

      {commitCount > 0 && (
        <div className="mb-4">
          <CommitList
            personId={personId}
            totalCommits={commitCount}
            prCount={prCount}
            from={from}
            to={to}
          />
        </div>
      )}
    </div>
  )
}
