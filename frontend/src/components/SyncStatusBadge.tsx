import { useState } from 'react'
import { postSyncRun } from '../api/client'
import { useQueryClient } from '@tanstack/react-query'

type SyncStatus = {
  sources: Array<{
    source: string
    last_success_at: string | null
    last_status: string
    events_count: number | null
  }>
}

function statusColor(state: string) {
  if (state === 'success') return 'bg-green-100 text-green-800'
  if (state === 'running') return 'bg-blue-100 text-blue-800'
  return 'bg-amber-100 text-amber-800'
}

export default function SyncStatusBadge({ status }: { status?: SyncStatus }) {
  const [syncing, setSyncing] = useState(false)
  const queryClient = useQueryClient()

  async function handleSyncNow() {
    setSyncing(true)
    try {
      await postSyncRun()
      await queryClient.invalidateQueries({ queryKey: ['syncStatus'] })
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="flex items-center gap-2">
      {status?.sources?.map(src => (
        <span
          key={src.source}
          className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(src.last_status)}`}
          title={src.last_success_at ? `Last synced: ${new Date(src.last_success_at).toLocaleString()}` : 'Never synced'}
        >
          {src.source}: {src.last_status}
        </span>
      ))}
      {!status?.sources?.length && (
        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-500">
          not synced
        </span>
      )}
      <button
        onClick={handleSyncNow}
        disabled={syncing}
        className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50 border border-blue-300 rounded px-2 py-0.5"
      >
        {syncing ? 'Syncing…' : 'Sync now'}
      </button>
    </div>
  )
}
