type SyncStatus = {
  sources: Array<{
    source: string
    last_success_at: string | null
    last_status: string
    events_count: number | null
  }>
}

export default function SyncStatusBadge({ status }: { status?: SyncStatus }) {
  const last = status?.sources?.[0]
  const state = last?.last_status || 'unknown'
  const color = state === 'success' ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'

  return (
    <div className="flex items-center gap-2">
      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
        {last?.source || 'sync'}: {state}
      </span>
    </div>
  )
}
