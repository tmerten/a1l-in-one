import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { usePersons, usePersonContributions } from '../hooks/useMetrics'
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

type Identity = { source: string; external_id: string }
type PersonMetrics = {
  commits: number; prs_merged: number; pr_loc_added: number; pr_loc_removed: number;
  issues_resolved: number; reviews_given: number; median_cycle_time_hours: number | null;
  sources: Record<string, Record<string, number>>
}
type Person = { id: string; display_name: string; identities: Identity[]; metrics: PersonMetrics }

type ProjectContribution = {
  project: string; commits: number; pull_requests: number;
  pr_loc_added: number; pr_loc_removed: number;
  issues_resolved: number; issues_opened: number; reviews_given: number;
}
type DatasourceContribution = {
  datasource: string; role: string; projects: ProjectContribution[]
}

export default function PeoplePage() {
  const [searchParams] = useSearchParams()
  const from = searchParams.get('from') ?? undefined
  const to = searchParams.get('to') ?? undefined
  const sprintId = searchParams.get('sprint_id') ?? undefined
  const datasource = searchParams.get('datasource') ?? undefined
  const project = searchParams.get('project') ?? undefined

  const query: Record<string, string | string[] | undefined> = {
    from, to, sprint_id: sprintId, datasource,
    projects: project ? [project] : undefined,
  }

  const { settings } = useSettings()
  const [selectedPerson, setSelectedPerson] = useState<string | null>(null)

  const { data: personsData, isLoading: pLoading } = usePersons(query)
  const { data: contributions, isLoading: cLoading } = usePersonContributions(selectedPerson || '', query)

  const persons: Person[] = personsData?.persons || []
  const allCommits = persons.map(p => p.metrics.commits)
  const allPRs = persons.map(p => p.metrics.prs_merged)
  const allIssues = persons.map(p => p.metrics.issues_resolved)
  const allCycleTimes = persons.map(p => p.metrics.median_cycle_time_hours).filter((v): v is number => v !== null)

  const medCommits = median(allCommits)
  const medPRs = median(allPRs)
  const medIssues = median(allIssues)
  const medCycle = median(allCycleTimes)

  function cell(value: number, med: number | null): string {
    return `px-4 py-2 text-right ${settings.outliers ? outlierClass(value, med) : 'text-gray-600'}`
  }

  const dsContributions: DatasourceContribution[] = contributions?.contributions || []
  const totalCommits = dsContributions.reduce((sum, ds) => sum + ds.projects.reduce((s, p) => s + p.commits, 0), 0)
  const totalPRs = dsContributions.reduce((sum, ds) => sum + ds.projects.reduce((s, p) => s + p.pull_requests, 0), 0)
  const totalIssuesResolved = dsContributions.reduce((sum, ds) => sum + ds.projects.reduce((s, p) => s + p.issues_resolved, 0), 0)
  const totalReviews = dsContributions.reduce((sum, ds) => sum + ds.projects.reduce((s, p) => s + p.reviews_given, 0), 0)
  const totalLocAdded = dsContributions.reduce((sum, ds) => sum + ds.projects.reduce((s, p) => s + p.pr_loc_added, 0), 0)
  const totalLocRemoved = dsContributions.reduce((sum, ds) => sum + ds.projects.reduce((s, p) => s + p.pr_loc_removed, 0), 0)

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">People Overview</h2>
        <SettingsPanel />
      </div>

      <section className="mb-6">
        <h3 className="text-sm font-medium text-gray-700 mb-2">Summary</h3>
        <div className="grid grid-cols-4 gap-4">
          <MetricCard title="Contributors" value={persons.length} loading={pLoading} />
          <MetricCard title="Total PRs Merged" value={persons.reduce((s, p) => s + p.metrics.prs_merged, 0)} loading={pLoading} />
          <MetricCard title="Issues Resolved" value={persons.reduce((s, p) => s + p.metrics.issues_resolved, 0)} loading={pLoading} />
          <MetricCard title="Median Cycle Time (hrs)" value={medCycle?.toFixed(1) ?? '—'} loading={pLoading} />
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
                <th className="px-4 py-2 text-right font-medium text-gray-700">LOC (+N/−M)</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Issues Resolved</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Reviews</th>
                <th className="px-4 py-2 text-right font-medium text-gray-700">Cycle Time (hrs)</th>
              </tr>
            </thead>
            <tbody>
              {persons.map((person) => (
                <tr
                  key={person.id}
                  className={`border-t border-gray-100 cursor-pointer hover:bg-gray-50 ${selectedPerson === person.id ? 'bg-blue-50' : ''}`}
                  onClick={() => setSelectedPerson(person.id === selectedPerson ? null : person.id)}
                  title={person.identities.map(i => `${i.source}: ${i.external_id}`).join('\n')}
                >
                  <td className="px-4 py-2 font-medium text-gray-900">
                    {person.display_name}
                    <div className="flex gap-1 mt-0.5">
                      {person.identities.map(i => (
                        <span key={i.source} className={`inline-block px-1 py-0 rounded text-[10px] ${
                          i.source === 'jira' ? 'bg-purple-100 text-purple-700' :
                          i.source === 'launchpad' ? 'bg-orange-100 text-orange-700' :
                          'bg-gray-100 text-gray-600'
                        }`}>
                          {i.source === 'jira' ? 'J' : i.source === 'launchpad' ? 'LP' : 'GH'}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className={cell(person.metrics.commits, medCommits)}>{person.metrics.commits}</td>
                  <td className={cell(person.metrics.prs_merged, medPRs)}>{person.metrics.prs_merged}</td>
                  <td className="px-4 py-2 text-right text-gray-600">
                    +{person.metrics.pr_loc_added.toLocaleString()} / −{person.metrics.pr_loc_removed.toLocaleString()}
                  </td>
                  <td className={cell(person.metrics.issues_resolved, medIssues)}>{person.metrics.issues_resolved}</td>
                  <td className={cell(person.metrics.reviews_given, null)}>{person.metrics.reviews_given}</td>
                  <td className="px-4 py-2 text-right text-gray-600">
                    {person.metrics.median_cycle_time_hours?.toFixed(1) ?? '—'}
                  </td>
                </tr>
              ))}
              {pLoading && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">Loading…</td></tr>
              )}
              {!pLoading && persons.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No data for this period</td></tr>
              )}
            </tbody>
          </table>
        </div>

        {selectedPerson && contributions && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <h4 className="font-medium text-gray-900">
                  {contributions.display_name}
                </h4>
                <div className="flex gap-1">
                  {contributions.identities?.map((i: Identity) => (
                    <span key={i.source} className={`inline-block px-1.5 py-0.5 rounded text-xs ${
                      i.source === 'jira' ? 'bg-purple-100 text-purple-700' :
                      i.source === 'launchpad' ? 'bg-orange-100 text-orange-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>
                      {i.source}: {i.external_id}
                    </span>
                  ))}
                </div>
              </div>
              <button onClick={() => setSelectedPerson(null)} className="text-sm text-blue-600 hover:underline">Clear</button>
            </div>

            <div className="grid grid-cols-4 gap-4 mb-4">
              <MetricCard title="Commits" value={totalCommits} loading={cLoading} />
              <MetricCard title="PRs Merged" value={totalPRs} loading={cLoading} />
              <MetricCard title="Issues Resolved" value={totalIssuesResolved} loading={cLoading} />
              <MetricCard title="Reviews Given" value={totalReviews} loading={cLoading} />
            </div>
            {totalLocAdded > 0 && (
              <div className="mb-4 text-xs text-gray-500">
                +{totalLocAdded.toLocaleString()} / −{totalLocRemoved.toLocaleString()} lines
              </div>
            )}

            {dsContributions.map((ds: DatasourceContribution) => (
              <div key={ds.datasource} className="mb-4">
                <h5 className="text-sm font-medium text-gray-800 mb-1">
                  <span className={`inline-block px-1.5 py-0.5 rounded text-xs mr-1.5 ${
                    ds.role === 'umbrella' ? 'bg-purple-100 text-purple-700' : 'bg-green-100 text-green-700'
                  }`}>
                    {ds.role === 'umbrella' ? 'Umbrella' : 'Code'}
                  </span>
                  {ds.datasource === 'jira' ? 'Jira' : ds.datasource === 'launchpad' ? 'Launchpad' : 'GitHub'}
                </h5>
                <div className="bg-white rounded border border-gray-200 overflow-hidden">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-1.5 text-left font-medium text-gray-600">Project</th>
                        {ds.role === 'code' && <th className="px-3 py-1.5 text-right font-medium text-gray-600">Commits</th>}
                        {ds.role === 'code' && <th className="px-3 py-1.5 text-right font-medium text-gray-600">PRs</th>}
                        {ds.role === 'code' && <th className="px-3 py-1.5 text-right font-medium text-gray-600">LOC</th>}
                        <th className="px-3 py-1.5 text-right font-medium text-gray-600">Issues Resolved</th>
                        {ds.role === 'code' && <th className="px-3 py-1.5 text-right font-medium text-gray-600">Reviews</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {ds.projects.map((p: ProjectContribution) => (
                        <tr key={p.project} className="border-t border-gray-100">
                          <td className="px-3 py-1.5 font-medium text-gray-700">{p.project}</td>
                          {ds.role === 'code' && <td className="px-3 py-1.5 text-right text-gray-600">{p.commits}</td>}
                          {ds.role === 'code' && <td className="px-3 py-1.5 text-right text-gray-600">{p.pull_requests}</td>}
                          {ds.role === 'code' && (
                            <td className="px-3 py-1.5 text-right text-gray-600">
                              +{p.pr_loc_added.toLocaleString()} / −{p.pr_loc_removed.toLocaleString()}
                            </td>
                          )}
                          <td className="px-3 py-1.5 text-right text-gray-600">{p.issues_resolved}</td>
                          {ds.role === 'code' && <td className="px-3 py-1.5 text-right text-gray-600">{p.reviews_given}</td>}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}

            {cLoading && <div className="text-center text-gray-400 py-4">Loading contributions…</div>}
          </div>
        )}
      </section>
    </div>
  )
}