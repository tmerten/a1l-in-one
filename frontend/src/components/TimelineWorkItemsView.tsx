import WorkItemCard from './WorkItemCard'
import CommitList from './CommitList'
import type { components } from '../api/types'

type WorkItem = components['schemas']['WorkItem']

interface TimelineWorkItemsViewProps {
  items: WorkItem[]
  personId: string
  from?: string
  to?: string
}

function formatDate(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
}

export default function TimelineWorkItemsView({ items, personId, from, to }: TimelineWorkItemsViewProps) {
  const nonCommitItems = items.filter(i => i.event_type !== 'commit')
  const commitCount = items.filter(i => i.event_type === 'commit').length
  const prCount = items.filter(i => i.event_type === 'pull_request').length

  const sorted = [...nonCommitItems].sort((a, b) =>
    new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  )

  const grouped: Record<string, WorkItem[]> = {}
  for (const item of sorted) {
    const day = formatDate(item.timestamp)
    if (!grouped[day]) grouped[day] = []
    grouped[day].push(item)
  }

  const days = Object.keys(grouped).sort((a, b) => {
    const dateA = new Date(a + ', 2024')
    const dateB = new Date(b + ', 2024')
    return dateB.getTime() - dateA.getTime()
  })

  return (
    <div className="relative">
      {days.map((day, dayIndex) => (
        <div key={day} className="relative pl-6 pb-6">
          {dayIndex < days.length - 1 && (
            <div className="absolute left-2 top-6 bottom-0 w-px bg-gray-200" />
          )}

          <div className="absolute left-0 top-1 w-4 h-4 rounded-full bg-gray-300 border-2 border-white" />

          <div className="font-medium text-gray-900 mb-3">{day}</div>

          <div className="space-y-3">
            {grouped[day].map(item => (
              <div key={item.id} className="flex items-start gap-3">
                <span className="text-xs text-gray-400 w-12 flex-shrink-0 pt-1">
                  {formatTime(item.timestamp)}
                </span>
                <div className="flex-1">
                  <WorkItemCard item={item} compact />
                </div>
              </div>
            ))}

            {commitCount > 0 && day === days[0] && (
              <div className="mt-4 ml-12">
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
        </div>
      ))}

      {sorted.length === 0 && commitCount > 0 && (
        <CommitList
          personId={personId}
          totalCommits={commitCount}
          prCount={prCount}
          from={from}
          to={to}
        />
      )}
    </div>
  )
}
