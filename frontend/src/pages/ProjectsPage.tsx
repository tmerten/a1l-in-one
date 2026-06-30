import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  useContributionVolume, useVelocity, useComposition, useCollaboration, useSprintBurndown,
  useContributionVolumeTs, useVelocityTs, useCollaborationTs,
} from '../hooks/useMetrics'
import MetricCard from '../components/MetricCard'
import SettingsPanel, { useSettings } from '../components/SettingsPanel'
import ChartSectionToggle from '../components/ChartSectionToggle'
import StackedBarChart from '../components/StackedBarChart'
import MultiLineChart from '../components/MultiLineChart'
import CollaborationGraph from '../components/CollaborationGraph'

const CHART_SKELETON = (
  <div className="h-[220px] rounded-md bg-gray-100 animate-pulse" />
)

export default function ProjectsPage() {
  const [searchParams] = useSearchParams()
  const from = searchParams.get('from') ?? undefined
  const to = searchParams.get('to') ?? undefined
  const sprintId = searchParams.get('sprint_id') ?? undefined
  const datasource = searchParams.get('datasource') ?? undefined
  const project = searchParams.get('project') ?? undefined
  const legacyProject = searchParams.get('projects') ?? undefined
  const effectiveProject = project || legacyProject
  const query = { from, to, sprint_id: sprintId, projects: effectiveProject ? [effectiveProject] : undefined, datasource }
  const tsQuery = { from, to, sprint_id: sprintId, datasource, project: effectiveProject }

  const { settings } = useSettings()

  // section view toggles
  const [volumeView, setVolumeView] = useState<'cards' | 'charts'>('cards')
  const [velocityView, setVelocityView] = useState<'cards' | 'charts'>('cards')
  const [collabView, setCollabView] = useState<'cards' | 'charts' | 'graph'>('cards')

  // series toggles
  const [volumeSeries, setVolumeSeries] = useState({ commits: true, prs: true, issues: true })
  const [velocitySeries, setVelocitySeries] = useState({ avg_cycle_hours: true })
  const [collabSeries, setCollabSeries] = useState({ reviews: true })

  // card data
  const { data: volume, isLoading: vLoading, error: vError } = useContributionVolume(query)
  const { data: velocity, isLoading: velLoading, error: velError } = useVelocity(query)
  const { data: composition, isLoading: cLoading, error: cError } = useComposition(query)
  const { data: collaboration, isLoading: colLoading, error: colError } = useCollaboration(query)
  const { data: burndown, isLoading: bLoading } = useSprintBurndown(sprintId || '')

  // time-series data
  const { data: volumeTs, isLoading: vtLoading } = useContributionVolumeTs(tsQuery)
  const { data: velocityTs, isLoading: veltLoading } = useVelocityTs(tsQuery)
  const { data: collabTs, isLoading: coltLoading } = useCollaborationTs(tsQuery)

  function toggleSeries<T extends Record<string, boolean>>(
    setter: React.Dispatch<React.SetStateAction<T>>,
    key: keyof T,
  ) {
    setter(prev => ({ ...prev, [key]: !prev[key] }))
  }

  // Map TS responses to chart data shape
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

      {settings.sections.volume && (
        <section className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-gray-700">Contribution Volume</h3>
            <ChartSectionToggle value={volumeView} onChange={setVolumeView} />
          </div>
          {volumeView === 'cards' ? (
            <>
              <div className="grid grid-cols-4 gap-4">
                <MetricCard title="Commits" value={volume?.commits ?? 0} loading={vLoading} error={vError?.message} />
                <MetricCard title="Change Requests" value={volume?.change_requests ?? volume?.pull_requests ?? 0} loading={vLoading} error={vError?.message} />
                <MetricCard title="Issues Opened" value={volume?.issues_opened ?? 0} loading={vLoading} error={vError?.message} />
                <MetricCard title="Issues Resolved" value={volume?.issues_resolved ?? 0} loading={vLoading} error={vError?.message} />
              </div>
              {volume && (
                <div className="mt-2 text-xs text-gray-500">
                  +{volume.additions.toLocaleString()} / −{volume.deletions.toLocaleString()} lines
                  &nbsp;·&nbsp;
                  {(volume.internal_ratio * 100).toFixed(0)}% internal
                </div>
              )}
            </>
          ) : vtLoading ? CHART_SKELETON : (
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
      )}

      {settings.sections.velocity && (
        <section className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-gray-700">Velocity & Throughput</h3>
            <ChartSectionToggle value={velocityView} onChange={setVelocityView} />
          </div>
          {velocityView === 'cards' ? (
            <>
              <div className="grid grid-cols-2 gap-4">
                <MetricCard title="Median Cycle Time (hrs)" value={velocity?.cycle_time_median?.toFixed(1) ?? '—'} loading={velLoading} error={velError?.message} />
                <MetricCard title="P90 Cycle Time (hrs)" value={velocity?.cycle_time_p90?.toFixed(1) ?? '—'} loading={velLoading} error={velError?.message} />
              </div>
              <div className="grid grid-cols-2 gap-4 mt-2">
                <MetricCard title="Median Review Turnaround (hrs)" value={velocity?.review_turnaround_median?.toFixed(1) ?? '—'} loading={velLoading} />
                <MetricCard title="P90 Review Turnaround (hrs)" value={velocity?.review_turnaround_p90?.toFixed(1) ?? '—'} loading={velLoading} />
              </div>
            </>
          ) : veltLoading ? CHART_SKELETON : (
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
      )}

      {settings.sections.composition && (
        <section className="mb-6">
          <h3 className="text-sm font-medium text-gray-700 mb-2">Quality & Composition</h3>
          <div className="grid grid-cols-2 gap-4">
            <MetricCard
              title="Issue Types"
              value={Object.entries(composition?.issue_types || {}).map(([k, v]) => `${k}: ${v}`).join(', ') || '—'}
              loading={cLoading}
              error={cError?.message}
            />
            <MetricCard
              title="Change Request Sizes"
              value={Object.entries(composition?.pr_sizes || {}).map(([k, v]) => `${k}: ${v}`).join(', ') || '—'}
              loading={cLoading}
              error={cError?.message}
            />
          </div>
        </section>
      )}

      {settings.sections.collaboration && (
        <section>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-medium text-gray-700">Collaboration</h3>
            <ChartSectionToggle
              value={collabView}
              onChange={setCollabView}
              options={['cards', 'charts', 'graph'] as const}
            />
          </div>
          {collabView === 'cards' ? (
            <MetricCard
              title="Review Pairs"
              value={Object.keys(collaboration?.review_matrix || {}).length}
              loading={colLoading}
              error={colError?.message}
            />
          ) : collabView === 'graph' ? (
            colLoading ? CHART_SKELETON : (
              <CollaborationGraph
                reviewMatrix={collaboration?.review_matrix}
                perPerson={collaboration?.per_person}
              />
            )
          ) : coltLoading ? CHART_SKELETON : (
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
      )}
    </div>
  )
}
