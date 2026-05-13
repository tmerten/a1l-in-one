import { useSearchParams } from 'react-router-dom'
import { useContributionVolume, useVelocity, useComposition, useCollaboration, useSprintBurndown } from '../hooks/useMetrics'
import MetricCard from '../components/MetricCard'
import SettingsPanel from '../components/SettingsPanel'

export default function ProjectsPage() {
  const [searchParams] = useSearchParams()
  const from = searchParams.get('from') || ''
  const to = searchParams.get('to') || ''
  const sprintId = searchParams.get('sprint_id') || ''
  const query = { from, to, sprint_id: sprintId }

  const { data: volume, isLoading: vLoading, error: vError } = useContributionVolume(query)
  const { data: velocity, isLoading: velLoading, error: velError } = useVelocity(query)
  const { data: composition, isLoading: cLoading, error: cError } = useComposition(query)
  const { data: collaboration, isLoading: colLoading, error: colError } = useCollaboration(query)
  const { data: burndown, isLoading: bLoading } = useSprintBurndown(sprintId)

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Projects Overview</h2>
        <SettingsPanel />
      </div>

      {sprintId && (
        <section className="mb-6">
          <h3 className="text-sm font-medium text-gray-700 mb-2">Sprint Burndown</h3>
          <div className="grid grid-cols-3 gap-4">
            <MetricCard title="Committed" value={burndown?.committed ?? '—'} loading={bLoading} />
            <MetricCard title="Completed" value={burndown?.completed ?? '—'} loading={bLoading} />
            <MetricCard title="Carried Over" value={burndown?.carried_over ?? '—'} loading={bLoading} />
          </div>
        </section>
      )}

      <section className="mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-2">Contribution Volume</h3>
        <div className="grid grid-cols-4 gap-4">
          <MetricCard title="Commits" value={volume?.commits ?? 0} loading={vLoading} error={vError?.message} />
          <MetricCard title="PRs" value={volume?.pull_requests ?? 0} loading={vLoading} error={vError?.message} />
          <MetricCard title="Issues Opened" value={volume?.issues_opened ?? 0} loading={vLoading} error={vError?.message} />
          <MetricCard title="Issues Resolved" value={volume?.issues_resolved ?? 0} loading={vLoading} error={vError?.message} />
        </div>
      </section>

      <section className="mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-2">Velocity & Throughput</h3>
        <div className="grid grid-cols-2 gap-4">
          <MetricCard title="Median Cycle Time (hrs)" value={velocity?.cycle_time_median?.toFixed(1) ?? '—'} loading={velLoading} error={velError?.message} />
          <MetricCard title="P90 Cycle Time (hrs)" value={velocity?.cycle_time_p90?.toFixed(1) ?? '—'} loading={velLoading} error={velError?.message} />
        </div>
      </section>

      <section className="mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-2">Quality & Composition</h3>
        <div className="grid grid-cols-2 gap-4">
          <MetricCard title="Issue Types" value={Object.entries(composition?.issue_types || {}).map(([k, v]) => `${k}: ${v}`).join(', ') || '—'} loading={cLoading} error={cError?.message} />
          <MetricCard title="PR Sizes" value={Object.entries(composition?.pr_sizes || {}).map(([k, v]) => `${k}: ${v}`).join(', ') || '—'} loading={cLoading} error={cError?.message} />
        </div>
      </section>

      <section>
        <h3 className="text-sm font-medium text-gray-700 mb-2">Collaboration</h3>
        <MetricCard title="Review Pairs" value={Object.keys(collaboration?.review_matrix || {}).length} loading={colLoading} error={colError?.message} />
      </section>
    </div>
  )
}
