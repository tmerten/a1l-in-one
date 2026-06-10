import { useSearchParams, useNavigate } from 'react-router-dom'
import { usePersons } from '../hooks/useMetrics'
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
  const navigate = useNavigate()

  const { data: personsData, isLoading: pLoading } = usePersons(query)

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
                  className="border-t border-gray-100 cursor-pointer hover:bg-gray-50"
                  onClick={() => navigate(`/persons/${person.id}${window.location.search}`)}
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

      </section>
    </div>
  )
}