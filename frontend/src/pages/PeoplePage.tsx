import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useContributionVolume, useVelocity, useComposition, useCollaboration } from '../hooks/useMetrics'
import MetricCard from '../components/MetricCard'
import SettingsPanel from '../components/SettingsPanel'

export default function PeoplePage() {
  const [searchParams] = useSearchParams()
  const from = searchParams.get('from') || ''
  const to = searchParams.get('to') || ''
  const query = { from, to }

  const [selectedPerson, setSelectedPerson] = useState<string | null>(null)

  const { data: volume, isLoading: vLoading } = useContributionVolume(query)
  const { data: velocity, isLoading: velLoading } = useVelocity(query)
  const { data: _composition } = useComposition(query)
  const { data: collaboration, isLoading: colLoading } = useCollaboration(query)

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">People Overview</h2>
        <SettingsPanel />
      </div>

      <section className="mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-2">Summary</h3>
        <div className="grid grid-cols-4 gap-4">
          <MetricCard title="Contributors" value={Object.keys(collaboration?.review_matrix || {}).length} loading={colLoading} />
          <MetricCard title="Median PRs" value={volume?.pull_requests ?? 0} loading={vLoading} />
          <MetricCard title="Issues Resolved" value={volume?.issues_resolved ?? 0} loading={vLoading} />
          <MetricCard title="Median Cycle Time" value={velocity?.cycle_time_median?.toFixed(1) ?? '—'} loading={velLoading} />
        </div>
      </section>

      <section className="mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-2">People</h3>
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-gray-700">Name</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Commits</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">PRs</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Issues</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Reviews</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries((collaboration?.per_person || {}) as Record<string, {reviews: number}>).map(([name, stats]) => (
                <tr
                  key={name}
                  className={`border-t border-gray-100 cursor-pointer hover:bg-gray-50 ${selectedPerson === name ? 'bg-blue-50' : ''}`}
                  onClick={() => setSelectedPerson(name === selectedPerson ? null : name)}
                >
                  <td className="px-4 py-2 font-medium text-gray-900">{name}</td>
                  <td className="px-4 py-2 text-right text-gray-600">{volume?.commits ?? 0}</td>
                  <td className="px-4 py-2 text-right text-gray-600">{volume?.pull_requests ?? 0}</td>
                  <td className="px-4 py-2 text-right text-gray-600">{volume?.issues_resolved ?? 0}</td>
                  <td className="px-4 py-2 text-right text-gray-600">{(stats as {reviews: number}).reviews}</td>
                </tr>
              ))}
              {colLoading && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Loading...</td></tr>
              )}
              {!colLoading && !collaboration?.per_person && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">No data for this period</td></tr>
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
            <div className="grid grid-cols-4 gap-4">
              <MetricCard title="Commits" value={volume?.commits ?? 0} />
              <MetricCard title="PRs" value={volume?.pull_requests ?? 0} />
              <MetricCard title="Cycle Time" value={velocity?.cycle_time_median?.toFixed(1) ?? '—'} />
              <MetricCard title="Reviews" value={collaboration?.per_person?.[selectedPerson]?.reviews ?? 0} />
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
