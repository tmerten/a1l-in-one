import { useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useProjects } from '../hooks/useMetrics'

type DatasourceGroup = {
  id: string
  role: string
  display_name: string
  projects: string[]
}

export default function DatasourceProjectFilter() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { data, isLoading } = useProjects()
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})

  const datasource = searchParams.get('datasource') ?? ''
  const project = searchParams.get('project') ?? ''

  const legacyProject = searchParams.get('projects') ?? ''
  const effectiveDatasource = datasource || (legacyProject ? inferDatasource(legacyProject, data?.datasources || []) : '')
  const effectiveProject = project || legacyProject

  const setFilter = useCallback((dsId: string, proj: string) => {
    const params = new URLSearchParams(searchParams)
    if (dsId && proj) {
      params.set('datasource', dsId)
      params.set('project', proj)
      params.delete('projects')
    } else if (dsId && !proj) {
      params.set('datasource', dsId)
      params.delete('project')
      params.delete('projects')
    } else {
      params.delete('datasource')
      params.delete('project')
      params.delete('projects')
    }
    setSearchParams(params, { replace: true })
  }, [searchParams, setSearchParams])

  const toggleGroup = useCallback((dsId: string) => {
    setExpandedGroups(prev => ({ ...prev, [dsId]: !prev[dsId] }))
  }, [])

  const datasources: DatasourceGroup[] = data?.datasources || []

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-500">Filter:</span>
      <div className="border border-gray-300 rounded-md bg-white min-w-[12rem] text-sm">
        <button
          className={`w-full px-3 py-1.5 text-left ${!effectiveDatasource ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-700'}`}
          onClick={() => setFilter('', '')}
          disabled={isLoading}
        >
          All sources
        </button>
        {datasources.map(ds => (
          <div key={ds.id} className="border-t border-gray-100">
            <button
              className={`w-full px-3 py-1 text-left flex items-center justify-between ${
                effectiveDatasource === ds.id && !effectiveProject
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-700 hover:bg-gray-50'
              }`}
              onClick={() => {
                if (expandedGroups[ds.id]) {
                  setFilter(ds.id, '')
                } else {
                  toggleGroup(ds.id)
                  setFilter(ds.id, '')
                }
              }}
              disabled={isLoading}
            >
              <span>
                <span className="inline-block px-1.5 py-0.5 rounded text-xs mr-1.5 ${
                  ds.role === 'umbrella' ? 'bg-purple-100 text-purple-700' : 'bg-green-100 text-green-700'
                }">
                  {ds.role === 'umbrella' ? 'U' : 'C'}
                </span>
                {ds.display_name}
              </span>
              <span className="text-gray-400">
                {expandedGroups[ds.id] ? '−' : '+'}
              </span>
            </button>
            {expandedGroups[ds.id] && ds.projects.map(p => (
              <button
                key={p}
                className={`w-full px-3 py-1 text-left pl-8 ${
                  effectiveDatasource === ds.id && effectiveProject === p
                    ? 'bg-blue-50 text-blue-700 font-medium'
                    : 'text-gray-600 hover:bg-gray-50'
                }`}
                onClick={() => setFilter(ds.id, p)}
                disabled={isLoading}
              >
                {p}
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

function inferDatasource(projectName: string, datasources: DatasourceGroup[]): string {
  for (const ds of datasources) {
    if (ds.projects.includes(projectName)) return ds.id
  }
  return ''
}