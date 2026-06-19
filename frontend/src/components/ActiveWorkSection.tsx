import WorkItemCard from './WorkItemCard'
import { useWorkItems } from '../hooks/useMetrics'
import type { components } from '../api/types'

type WorkItem = components['schemas']['WorkItem']

interface ActiveWorkSectionProps {
  personId: string
}

export default function ActiveWorkSection({ personId }: ActiveWorkSectionProps) {
  const { data, isLoading, error } = useWorkItems(personId, {
    status: 'active',
    per_page: 20,
  })

  const items = data?.items || []

  if (isLoading) {
    return (
      <div className="mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Active Work</h3>
        <div className="animate-pulse space-y-2">
          <div className="h-16 bg-gray-100 rounded" />
          <div className="h-16 bg-gray-100 rounded" />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Active Work</h3>
        <div className="text-sm text-red-600">Failed to load active work items</div>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-3">Active Work</h3>
        <div className="text-sm text-gray-500 italic">No active work items</div>
      </div>
    )
  }

  return (
    <div className="mb-6">
      <h3 className="text-sm font-medium text-gray-700 mb-3">
        Active Work ({items.length})
      </h3>
      <div className="space-y-2">
        {items.map((item: WorkItem) => (
          <WorkItemCard key={item.id} item={item} />
        ))}
      </div>
    </div>
  )
}
