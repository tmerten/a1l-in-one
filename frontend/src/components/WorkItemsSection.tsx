import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useWorkItems } from '../hooks/useMetrics'
import ActiveWorkSection from './ActiveWorkSection'
import GroupedWorkItemsView from './GroupedWorkItemsView'
import TimelineWorkItemsView from './TimelineWorkItemsView'
import ViewToggle from './ViewToggle'

interface WorkItemsSectionProps {
  personId: string
  from?: string
  to?: string
  sprintId?: string
}

export default function WorkItemsSection({ personId, from, to, sprintId }: WorkItemsSectionProps) {
  const [searchParams] = useSearchParams()
  const [collapsed, setCollapsed] = useState(false)
  const sectionRef = useRef<HTMLDivElement>(null)

  const shouldScroll = searchParams.get('section') === 'work-items'
  useEffect(() => {
    if (shouldScroll && sectionRef.current) {
      sectionRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [shouldScroll])

  const view = searchParams.get('view') as 'grouped' | 'timeline' | null

  const { data, isLoading, error } = useWorkItems(personId, {
    status: 'completed',
    from,
    to,
    per_page: 100,
  })

  const items = data?.items || []
  const total = data?.total || 0

  const timeframeLabel = sprintId
    ? 'Sprint'
    : from && to
      ? `${from} – ${to}`
      : 'Last 30 days'

  const shippedLabel = sprintId
    ? 'Shipped This Sprint'
    : from && to
      ? `Shipped ${from} – ${to}`
      : 'Shipped Last 30 Days'

  return (
    <div ref={sectionRef} className="mt-8">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <button
            className="flex items-center gap-2 text-gray-400 hover:text-gray-600"
            onClick={() => setCollapsed(!collapsed)}
          >
            <span>{collapsed ? '▸' : '▾'}</span>
          </button>
          <h2 className="text-lg font-semibold text-gray-900">Work Items</h2>
          <span className="text-sm text-gray-500">{timeframeLabel}</span>
          <span className="text-sm text-gray-400">• {total} items</span>
        </div>
        <ViewToggle defaultValue="grouped" />
      </div>

      {!collapsed && (
        <>
          {isLoading && (
            <div className="animate-pulse space-y-4">
              <div className="h-20 bg-gray-100 rounded" />
              <div className="h-20 bg-gray-100 rounded" />
            </div>
          )}

          {error && (
            <div className="text-sm text-red-600 p-4">
              Failed to load work items
            </div>
          )}

          {!isLoading && !error && (
            <>
              <ActiveWorkSection personId={personId} />
              <div className="mt-6">
                <h3 className="text-sm font-semibold text-gray-700 mb-3">
                  {shippedLabel}
                </h3>
                {view === 'timeline' ? (
                  <TimelineWorkItemsView
                    items={items}
                    personId={personId}
                    from={from}
                    to={to}
                  />
                ) : (
                  <GroupedWorkItemsView
                    items={items}
                    personId={personId}
                    from={from}
                    to={to}
                  />
                )}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
