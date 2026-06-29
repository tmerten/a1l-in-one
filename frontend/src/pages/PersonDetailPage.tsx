import { useState } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import { usePersonContributions, useContributionVolumeTs, useVelocityTs, useCollaborationTs } from '../hooks/useMetrics'
import MetricCard from '../components/MetricCard'
import StackedBarChart from '../components/StackedBarChart'
import MultiLineChart from '../components/MultiLineChart'
import WorkItemsSection from '../components/WorkItemsSection'

type Identity = { source: string; external_id: string }
type ProjectContribution = {
  project: string; commits: number; pull_requests: number;
  pr_loc_added: number; pr_loc_removed: number;
  issues_resolved: number; issues_opened: number; reviews_given: number;
}
type DatasourceContribution = { datasource: string; role: string; projects: ProjectContribution[] }

const CHART_SKELETON = <div className="h-[220px] rounded-md bg-gray-100 animate-pulse" />

export default function PersonDetailPage() {
  const { personId } = useParams<{ personId: string }>()
  const [searchParams] = useSearchParams()
  const from = searchParams.get('from') ?? undefined
  const to = searchParams.get('to') ?? undefined
  const sprintId = searchParams.get('sprint_id') ?? undefined
  const datasource = searchParams.get('datasource') ?? undefined
  const project = searchParams.get('project') ?? undefined

  const query = { from, to, sprint_id: sprintId, datasource, projects: project ? [project] : undefined }
  const tsBase = { from, to, sprint_id: sprintId, datasource }

  const { data: contributions, isLoading: cLoading, error: cError } = usePersonContributions(personId ?? '', query)

  // Extract GitHub actor for time-series filtering
  const githubIdentity = contributions?.identities?.find((i: Identity) => i.source === 'github')
  const githubLogin = githubIdentity?.external_id as string | undefined
  const tsQuery = githubLogin ? { ...tsBase, actors: [githubLogin] } : null

  // Time-series data (only fetched when we have a GitHub identity)
  const { data: volumeTs, isLoading: vtLoading } = useContributionVolumeTs(tsQuery ?? {})
  const { data: velocityTs, isLoading: veltLoading } = useVelocityTs(tsQuery ?? {})
  const { data: collabTs, isLoading: coltLoading } = useCollaborationTs(tsQuery ?? {})

  // Series toggles
  const [volumeSeries, setVolumeSeries] = useState({ commits: true, prs: true, issues: true })
  const [velocitySeries, setVelocitySeries] = useState({ avg_cycle_hours: true })
  const [collabSeries, setCollabSeries] = useState({ reviews: true })

  function toggleSeries<T extends Record<string, boolean>>(
    setter: React.Dispatch<React.SetStateAction<T>>,
    key: keyof T,
  ) {
    setter(prev => ({ ...prev, [key]: !prev[key] }))
  }

  if (cLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
        Loading…
      </div>
    )
  }

  if (cError || !contributions) {
    return (
      <div className="text-sm text-red-600 p-4">
        Could not load person data.{' '}
        <Link to="/people" className="underline text-blue-600">Back to People</Link>
      </div>
    )
  }

  // Aggregate totals from contributions
  const dsContributions: DatasourceContribution[] = contributions.contributions ?? []
  const totalCommits = dsContributions.reduce((s, ds) => s + ds.projects.reduce((sp, p) => sp + p.commits, 0), 0)
  const totalChangeRequests = dsContributions.reduce((s, ds) => s + ds.projects.reduce((sp, p) => sp + p.pull_requests, 0), 0)
  const totalIssuesResolved = dsContributions.reduce((s, ds) => s + ds.projects.reduce((sp, p) => sp + p.issues_resolved, 0), 0)
  const totalReviews = dsContributions.reduce((s, ds) => s + ds.projects.reduce((sp, p) => sp + p.reviews_given, 0), 0)

  // Map TS data to chart shape
  const volumeChartData = (volumeTs?.data ?? []).map((p: { bucket: string; value: { commits: number; prs: number; issues: number } }) => ({
    bucket: p.bucket,
    commits: p.value.commits,
    prs: p.value.prs,
    issues: p.value.issues,
  }))
  const velocityChartData = (velocityTs?.data ?? []).map((p: { bucket: string; value: { avg_cycle_hours: number | null } }) => ({
    bucket: p.bucket,
    avg_cycle_hours: p.value.avg_cycle_hours,
  }))
  const collabChartData = (collabTs?.data ?? []).map((p: { bucket: string; value: { reviews: number } }) => ({
    bucket: p.bucket,
    reviews: p.value.reviews,
  }))

  const noCharts = !githubLogin

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <Link to="/people" className="text-sm text-blue-600 hover:underline">← People</Link>
        <div className="flex items-center gap-3 mt-2">
          <h2 className="text-lg font-semibold text-gray-900">{contributions.display_name}</h2>
          <div className="flex gap-1">
            {contributions.identities?.map((i: Identity) => (
              <span
                key={i.source}
                className={`inline-block px-1.5 py-0.5 rounded text-xs ${
                  i.source === 'jira' ? 'bg-purple-100 text-purple-700' :
                  i.source === 'launchpad' ? 'bg-orange-100 text-orange-700' :
                  'bg-gray-100 text-gray-600'
                }`}
              >
                {i.source}: {i.external_id}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Summary cards */}
      <section className="mb-6">
        <div className="grid grid-cols-4 gap-4">
          <MetricCard title="Commits" value={totalCommits} loading={cLoading} />
          <MetricCard title="Change Requests" value={totalChangeRequests} loading={cLoading} />
          <MetricCard title="Issues Resolved" value={totalIssuesResolved} loading={cLoading} />
          <MetricCard title="Reviews Given" value={totalReviews} loading={cLoading} />
        </div>
      </section>

      {noCharts ? (
        <div className="rounded-md bg-amber-50 border border-amber-200 text-amber-700 text-sm px-4 py-3">
          Chart data not available — no GitHub identity linked to this person.
        </div>
      ) : (
        <>
          {/* Contribution Volume chart */}
          <section className="mb-6">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Contribution Volume over time</h3>
            {vtLoading ? CHART_SKELETON : (
              <StackedBarChart
                data={volumeChartData}
                bucketSize={volumeTs?.bucket_size ?? 'day'}
                series={[
                  { key: 'commits', label: 'Commits', color: '#6366f1', visible: volumeSeries.commits },
                  { key: 'prs', label: 'Change Requests', color: '#10b981', visible: volumeSeries.prs },
                  { key: 'issues', label: 'Issues', color: '#f59e0b', visible: volumeSeries.issues },
                ]}
                onToggle={key => toggleSeries(setVolumeSeries, key as keyof typeof volumeSeries)}
              />
            )}
          </section>

          {/* Velocity chart */}
          <section className="mb-6">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Velocity over time</h3>
            {veltLoading ? CHART_SKELETON : (
              <MultiLineChart
                data={velocityChartData}
                bucketSize={velocityTs?.bucket_size ?? 'day'}
                unit="hrs"
                series={[
                  { key: 'avg_cycle_hours', label: 'Avg Cycle Time', color: '#8b5cf6', visible: velocitySeries.avg_cycle_hours },
                ]}
                onToggle={key => toggleSeries(setVelocitySeries, key as keyof typeof velocitySeries)}
              />
            )}
          </section>

          {/* Collaboration chart */}
          <section className="mb-6">
            <h3 className="text-sm font-medium text-gray-700 mb-3">Collaboration over time</h3>
            {coltLoading ? CHART_SKELETON : (
              <StackedBarChart
                data={collabChartData}
                bucketSize={collabTs?.bucket_size ?? 'day'}
                series={[
                  { key: 'reviews', label: 'Reviews', color: '#3b82f6', visible: collabSeries.reviews },
                ]}
                onToggle={key => toggleSeries(setCollabSeries, key as keyof typeof collabSeries)}
              />
            )}
          </section>
        </>
      )}

      <WorkItemsSection
        personId={personId ?? ''}
        from={from}
        to={to}
        sprintId={sprintId}
      />
    </div>
  )
}
