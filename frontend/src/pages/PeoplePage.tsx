import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useContributionVolume, useVelocity, useCollaboration } from '../hooks/useMetrics'
import MetricCard from '../components/MetricCard'
import SettingsPanel, { useSettings } from '../components/SettingsPanel'

function median(values: number[]): number | null {
  if (!values.length) return null
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid]
}

function outlierClass(value: number, med: number | null): string {
  if (med === null || med === 0) return 'text-gray-600'
  if (value > med * 1.5) return 'text-green-700 bg-green-50'
  if (value < med * 0.5) return 'text-red-700 bg-red-50'
  return 'text-gray-600'
}

export default function PeoplePage() {
  const [searchParams] = useSearchParams()
  const from = searchParams.get('from') ?? undefined
  const to = searchParams.get('to') ?? undefined
  const sprintId = searchParams.get('sprint_id') ?? undefined
  const project = searchParams.get('projects') ?? undefined
  const query = { from, to, sprint_id: sprintId, projects: project ? [project] : undefined }

  const { settings } = useSettings()
  const [selectedPerson, setSelectedPerson] = useState<string | null>(null)

  const { data: volume, isLoading: vLoading } = useContributionVolume(query)
  const { data: velocity, isLoading: velLoading } = useVelocity(query)
  const { data: collaboration, isLoading: colLoading } = useCollaboration(query)

  // Per-person query (actors filter) for selected person
  const personQuery = { ...query, actors: selectedPerson || undefined }
  const { data: personVolume, isLoading: pvLoading } = useContributionVolume(personQuery)
  const { data: personVelocity, isLoading: pvelLoading } = useVelocity(personQuery)

  type PersonStats = { reviews: number; comments: number }
  const perPerson = (collaboration?.per_person || {}) as Record<string, PersonStats>

  const allStats = Object.values(perPerson)
  const medReviews = median(allStats.map(s => s.reviews))
  const medComments = median(allStats.map(s => s.comments))
  const medRatios = median(allStats.map(s => s.reviews > 0 ? s.comments / s.reviews : 0))

  function cell(value: number, med: number | null): string {
    return `px-4 py-2 text-right ${settings.outliers ? outlierClass(value, med) : 'text-gray-600'}`
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">People Overview</h2>
        <SettingsPanel />
      </div>

      <section className="mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-2">Summary</h3>
        <div className="grid grid-cols-4 gap-4">
          <MetricCard title="Contributors" value={Object.keys(perPerson).length} loading={colLoading} />
          <MetricCard title="Total PRs" value={volume?.pull_requests ?? 0} loading={vLoading} />
          <MetricCard title="Issues Resolved" value={volume?.issues_resolved ?? 0} loading={vLoading} />
          <MetricCard title="Median Cycle Time (hrs)" value={velocity?.cycle_time_median?.toFixed(1) ?? '—'} loading={velLoading} />
        </div>
      </section>

      <section className="mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-2">People</h3>
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Name</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Reviews</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Comments</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Comments/Review</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(perPerson).map(([name, stats]) => (
                <tr
                  key={name}
                  className={`border-t border-gray-100 cursor-pointer hover:bg-gray-50 ${selectedPerson === name ? 'bg-blue-50' : ''}`}
                  onClick={() => setSelectedPerson(name === selectedPerson ? null : name)}
                >
                  <td className="px-4 py-2 font-medium text-gray-900">{name}</td>
                  <td className={cell(stats.reviews, medReviews)}>{stats.reviews}</td>
                  <td className={cell(stats.comments, medComments)}>{stats.comments}</td>
                  <td className={cell(stats.reviews > 0 ? stats.comments / stats.reviews : 0, medRatios)}>
                    {stats.reviews > 0 ? (stats.comments / stats.reviews).toFixed(1) : '—'}
                  </td>
                </tr>
              ))}
              {colLoading && (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400">Loading…</td></tr>
              )}
              {!colLoading && Object.keys(perPerson).length === 0 && (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400">No data for this period</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {selectedPerson && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-medium text-gray-900">{selectedPerson}</h4>
              <button onClick={() => setSelectedPerson(null)} className="text-sm text-blue-600 hover:underline">Clear</button>
            </div>
            {settings.sections.volume && (
              <div className="grid grid-cols-4 gap-4 mb-3">
                <MetricCard title="Commits" value={personVolume?.commits ?? '—'} loading={pvLoading} />
                <MetricCard title="PRs" value={personVolume?.pull_requests ?? '—'} loading={pvLoading} />
                <MetricCard title="Issues Resolved" value={personVolume?.issues_resolved ?? '—'} loading={pvLoading} />
                <MetricCard title="Cycle Time (hrs)" value={personVelocity?.cycle_time_median?.toFixed(1) ?? '—'} loading={pvelLoading} />
              </div>
            )}
            {settings.sections.collaboration && (
              <div className="grid grid-cols-3 gap-4">
                <MetricCard title="Reviews Given" value={perPerson[selectedPerson]?.reviews ?? 0} />
                <MetricCard title="Comments" value={perPerson[selectedPerson]?.comments ?? 0} />
                <MetricCard
                  title="Comments/Review"
                  value={
                    perPerson[selectedPerson]?.reviews > 0
                      ? (perPerson[selectedPerson].comments / perPerson[selectedPerson].reviews).toFixed(1)
                      : '—'
                  }
                />
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  )
}
