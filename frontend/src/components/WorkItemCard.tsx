import { useState } from 'react'
import type { components } from '../api/types'

type WorkItem = components['schemas']['WorkItem']

interface WorkItemCardProps {
  item: WorkItem
  compact?: boolean
}

function DatasourceBadge({ datasource }: { datasource: string }) {
  if (datasource === 'jira') {
    return <span className="inline-block px-1.5 py-0.5 rounded text-xs font-medium bg-purple-100 text-purple-700">Jira</span>
  }
  if (datasource === 'launchpad') {
    return <span className="inline-block px-1.5 py-0.5 rounded text-xs font-medium bg-orange-100 text-orange-700">LP</span>
  }
  return <span className="inline-block px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">GH</span>
}

function StatusBadge({ status }: { status: string }) {
  const lower = status.toLowerCase()
  if (lower === 'merged' || lower === 'done' || lower === 'closed') {
    return <span className="inline-block px-1.5 py-0.5 rounded text-xs bg-green-100 text-green-700">{status}</span>
  }
  if (lower === 'draft') {
    return <span className="inline-block px-1.5 py-0.5 rounded text-xs bg-yellow-100 text-yellow-700">{status}</span>
  }
  if (lower === 'open' || lower === 'in progress') {
    return <span className="inline-block px-1.5 py-0.5 rounded text-xs bg-blue-100 text-blue-700">{status}</span>
  }
  return <span className="inline-block px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-600">{status}</span>
}

function relativeTime(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 30) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

export default function WorkItemCard({ item, compact = false }: WorkItemCardProps) {
  const [expanded, setExpanded] = useState(false)
  const { datasource, event_type, external_id, project, title, description, status, timestamp, url, metadata } = item

  let iconLabel = ''
  if (event_type === 'pull_request') iconLabel = 'PR'
  else if (event_type === 'issue') iconLabel = 'Issue'
  else if (event_type === 'commit') iconLabel = 'Commit'
  else if (event_type === 'pull_request_review') iconLabel = 'Review'
  else iconLabel = event_type

  const chips: string[] = []
  if (metadata?.additions != null && metadata?.deletions != null) {
    chips.push(`+${metadata.additions} -${metadata.deletions}`)
  }
  if (metadata?.story_points != null) {
    chips.push(`${metadata.story_points} pts`)
  }
  if (metadata?.issue_type) {
    chips.push(metadata.issue_type)
  }
  if (metadata?.reviewers && metadata.reviewers.length > 0) {
    chips.push(`${metadata.reviewers.length} reviewers`)
  }

  const maxDescLen = compact ? 60 : 120
  const truncatedDesc = description && description.length > maxDescLen
    ? description.slice(0, maxDescLen) + '...'
    : description

  const displayId = event_type === 'commit' ? (metadata?.sha || external_id.slice(0, 7)) : external_id

  if (compact) {
    const idLink = url ? (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-gray-500 text-xs hover:text-blue-600 font-mono"
        onClick={(e) => e.stopPropagation()}
      >
        {iconLabel} {displayId}
      </a>
    ) : (
      <span className="text-gray-500 text-xs font-mono">{iconLabel} {displayId}</span>
    )

    const prLink = metadata?.pr_number && (event_type === 'commit' || event_type === 'pull_request_review') && (
      <a
        href={`https://github.com/${project}/pull/${metadata.pr_number}`}
        target="_blank"
        rel="noopener noreferrer"
        className="text-gray-400 text-xs hover:text-blue-600"
        onClick={(e) => e.stopPropagation()}
      >
        PR #{metadata.pr_number}
      </a>
    )

    return (
      <div className="flex items-center gap-2 text-sm py-1.5 px-2 hover:bg-gray-50 rounded">
        <DatasourceBadge datasource={datasource} />
        {idLink}
        {prLink && <span className="text-gray-400">•</span>}
        {prLink}
        <span className="flex-1 truncate text-gray-900">{title}</span>
        <StatusBadge status={status} />
        <span className="text-xs text-gray-400">{relativeTime(timestamp)}</span>
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-800 text-xs"
            onClick={(e) => e.stopPropagation()}
          >
            ↗
          </a>
        )}
      </div>
    )
  }

  return (
    <div className="border border-gray-200 rounded-lg p-3 bg-white hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <DatasourceBadge datasource={datasource} />
          <span className="text-xs text-gray-500">{project}</span>
        </div>
        <StatusBadge status={status} />
      </div>

      <div className="mt-1.5">
        <h4 className="text-sm font-medium text-gray-900">{title}</h4>
      </div>

      {truncatedDesc && (
        <p
          className="mt-1 text-xs text-gray-500 cursor-pointer"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? description : truncatedDesc}
          {description && description.length > maxDescLen && (
            <span className="text-blue-600 ml-1">{expanded ? 'Show less' : 'Show more'}</span>
          )}
        </p>
      )}

      <div className="mt-2 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          {url ? (
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-blue-600 font-mono"
              onClick={(e) => e.stopPropagation()}
            >
              {iconLabel} {displayId}
            </a>
          ) : (
            <span className="font-mono">{iconLabel} {displayId}</span>
          )}
          {metadata?.pr_number && (event_type === 'commit' || event_type === 'pull_request_review') && (
            <>
              <span>•</span>
              <a
                href={`https://github.com/${project}/pull/${metadata.pr_number}`}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-blue-600"
                onClick={(e) => e.stopPropagation()}
              >
                PR #{metadata.pr_number}
              </a>
            </>
          )}
          <span>•</span>
          <span>{relativeTime(timestamp)}</span>
          {chips.length > 0 && (
            <>
              <span>•</span>
              <span>{chips.join(' • ')}</span>
            </>
          )}
        </div>
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-0.5"
          >
            Open <span className="text-xs">↗</span>
          </a>
        )}
      </div>
    </div>
  )
}
