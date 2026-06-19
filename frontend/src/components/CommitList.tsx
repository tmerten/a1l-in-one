import { useState } from 'react'
import { useCommits } from '../hooks/useMetrics'
import type { components } from '../api/types'

type CommitItem = components['schemas']['CommitItem']

interface CommitListProps {
  personId: string
  totalCommits: number
  prCount: number
  from?: string
  to?: string
}

function formatDate(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

export default function CommitList({ personId, totalCommits, prCount, from, to }: CommitListProps) {
  const [expanded, setExpanded] = useState(false)

  const { data, isLoading, error } = useCommits(personId, {
    from,
    to,
    page: 1,
    per_page: 100,
  })

  if (totalCommits === 0) {
    return null
  }

  const commits: CommitItem[] = data?.items || []

  const grouped: Record<string, CommitItem[]> = {}
  for (const commit of commits) {
    const day = formatDate(commit.timestamp)
    if (!grouped[day]) grouped[day] = []
    grouped[day].push(commit)
  }

  return (
    <div className="mb-4">
      <button
        className="flex items-center gap-2 text-sm font-medium text-gray-700 mb-2"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-gray-400">{expanded ? '▾' : '▸'}</span>
        Commits ({totalCommits}) across {prCount} PRs
      </button>

      {expanded && (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          {isLoading && (
            <div className="p-4 text-center text-gray-400 text-sm">Loading commits...</div>
          )}
          {error && (
            <div className="p-4 text-center text-red-600 text-sm">Failed to load commits</div>
          )}
          {!isLoading && !error && Object.entries(grouped).map(([day, dayCommits]) => (
            <div key={day} className="border-b border-gray-100 last:border-b-0">
              <div className="px-4 py-2 bg-gray-50 text-xs font-medium text-gray-600">
                {day} • {dayCommits.length} commits
              </div>
              <div className="divide-y divide-gray-100">
                {dayCommits.slice(0, 5).map((commit) => (
                  <div key={commit.id} className="flex items-center gap-3 px-4 py-2 hover:bg-gray-50">
                    {commit.url ? (
                      <a
                        href={commit.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-gray-500 font-mono hover:text-blue-600"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {commit.sha}
                      </a>
                    ) : (
                      <code className="text-xs text-gray-500 font-mono">{commit.sha}</code>
                    )}
                    <span className="flex-1 text-sm text-gray-700 truncate">{commit.message}</span>
                    {commit.pr_number && (
                      <a
                        href={`https://github.com/${commit.project}/pull/${commit.pr_number}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-gray-400 hover:text-blue-600"
                        onClick={(e) => e.stopPropagation()}
                      >
                        PR #{commit.pr_number}
                      </a>
                    )}
                    {commit.url && (
                      <a
                        href={commit.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:text-blue-800"
                        onClick={(e) => e.stopPropagation()}
                      >
                        ↗
                      </a>
                    )}
                  </div>
                ))}
                {dayCommits.length > 5 && (
                  <div className="px-4 py-2 text-xs text-gray-400 text-center">
                    ... {dayCommits.length - 5} more commits
                  </div>
                )}
              </div>
            </div>
          ))}
          {commits.length > 0 && commits[0]?.url && (
            <div className="px-4 py-2 bg-gray-50 border-t border-gray-200">
              <a
                href={commits[0].url.replace(/\/commit\/.+$/, '/commits')}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-blue-600 hover:text-blue-800"
              >
                View all commits on GitHub ↗
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
