import { useState, useCallback, useRef, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useProjects } from '../hooks/useMetrics'
import type { components } from '../api/types'

type DatasourceGroup = components['schemas']['DatasourceProjectGroup']

export default function DatasourceProjectFilter() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { data, isLoading } = useProjects()
  const [open, setOpen] = useState(false)
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({})
  const ref = useRef<HTMLDivElement>(null)

  const datasource = searchParams.get('datasource') ?? ''
  const project = searchParams.get('project') ?? ''
  const legacyProject = searchParams.get('projects') ?? ''
  const effectiveDatasource = datasource || (legacyProject ? inferDatasource(legacyProject, data?.datasources || []) : '')
  const effectiveProject = project || legacyProject

  // Close on outside click
  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [])

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
    setOpen(false)
  }, [searchParams, setSearchParams])

  const toggleGroup = useCallback((dsId: string) => {
    setExpandedGroups(prev => ({ ...prev, [dsId]: !prev[dsId] }))
  }, [])

  const datasources: DatasourceGroup[] = data?.datasources || []

  // Build trigger label
  let triggerLabel = 'All sources'
  if (effectiveDatasource) {
    const ds = datasources.find(d => d.id === effectiveDatasource)
    triggerLabel = effectiveProject
      ? `${ds?.display_name ?? effectiveDatasource}: ${effectiveProject}`
      : (ds?.display_name ?? effectiveDatasource)
  }

  return (
    <div className="flex items-center gap-2" ref={ref}>
      <span className="text-sm text-gray-500">Filter:</span>
      <div className="relative">
        <button
          onClick={() => setOpen(v => !v)}
          disabled={isLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white text-gray-700 hover:bg-gray-50 min-w-[10rem] text-left"
        >
          <span className="flex-1 truncate">{isLoading ? 'Loading…' : triggerLabel}</span>
          <span className="text-gray-400 text-xs">{open ? '▲' : '▼'}</span>
        </button>

        {open && (
          <div className="absolute right-0 top-full mt-1 z-50 border border-gray-200 rounded-md bg-white shadow-lg min-w-[14rem] text-sm">
            <button
              className={`w-full px-3 py-1.5 text-left ${!effectiveDatasource ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-700 hover:bg-gray-50'}`}
              onClick={() => setFilter('', '')}
            >
              All sources
            </button>
            {datasources.map(ds => (
              <div key={ds.id} className="border-t border-gray-100">
                <button
                  className={`w-full px-3 py-1.5 text-left flex items-center justify-between ${
                    effectiveDatasource === ds.id && !effectiveProject
                      ? 'bg-blue-50 text-blue-700 font-medium'
                      : 'text-gray-700 hover:bg-gray-50'
                  }`}
                  onClick={() => {
                    if (!expandedGroups[ds.id]) toggleGroup(ds.id)
                    setFilter(ds.id, '')
                    setOpen(true)
                  }}
                >
                  <span className="flex items-center gap-1.5">
                    <span className={`inline-block px-1.5 py-0.5 rounded text-xs ${
                      ds.role === 'umbrella' ? 'bg-purple-100 text-purple-700' : 'bg-green-100 text-green-700'
                    }`}>
                      {ds.role === 'umbrella' ? 'U' : 'C'}
                    </span>
                    {ds.display_name}
                  </span>
                  <button
                    className="text-gray-400 px-1"
                    onClick={e => { e.stopPropagation(); toggleGroup(ds.id) }}
                    aria-label={expandedGroups[ds.id] ? 'Collapse' : 'Expand'}
                  >
                    {expandedGroups[ds.id] ? '−' : '+'}
                  </button>
                </button>
                {expandedGroups[ds.id] && renderDatasourceTargets(ds, effectiveDatasource, effectiveProject, setFilter)}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function renderDatasourceTargets(
  ds: DatasourceGroup,
  effectiveDatasource: string,
  effectiveProject: string,
  setFilter: (dsId: string, proj: string) => void,
) {
  if (ds.id === 'launchpad' && ((ds.bug_targets?.length ?? 0) > 0 || (ds.repositories?.length ?? 0) > 0)) {
    return (
      <>
        <TargetGroup
          label="Bug targets"
          targets={ds.bug_targets ?? []}
          datasourceId={ds.id}
          effectiveDatasource={effectiveDatasource}
          effectiveProject={effectiveProject}
          setFilter={setFilter}
        />
        <TargetGroup
          label="Repositories"
          targets={ds.repositories ?? []}
          datasourceId={ds.id}
          effectiveDatasource={effectiveDatasource}
          effectiveProject={effectiveProject}
          setFilter={setFilter}
        />
      </>
    )
  }

  return (ds.projects ?? []).map(p => (
    <TargetButton
      key={p}
      datasourceId={ds.id}
      target={p}
      effectiveDatasource={effectiveDatasource}
      effectiveProject={effectiveProject}
      setFilter={setFilter}
    />
  ))
}

function TargetGroup({ label, targets, datasourceId, effectiveDatasource, effectiveProject, setFilter }: {
  label: string
  targets: string[]
  datasourceId: string
  effectiveDatasource: string
  effectiveProject: string
  setFilter: (dsId: string, proj: string) => void
}) {
  if (targets.length === 0) return null
  return (
    <div>
      <div className="px-3 py-1 pl-9 text-[11px] uppercase tracking-wide text-gray-400 bg-gray-50">
        {label}
      </div>
      {targets.map(target => (
        <TargetButton
          key={target}
          datasourceId={datasourceId}
          target={target}
          effectiveDatasource={effectiveDatasource}
          effectiveProject={effectiveProject}
          setFilter={setFilter}
        />
      ))}
    </div>
  )
}

function TargetButton({ datasourceId, target, effectiveDatasource, effectiveProject, setFilter }: {
  datasourceId: string
  target: string
  effectiveDatasource: string
  effectiveProject: string
  setFilter: (dsId: string, proj: string) => void
}) {
  return (
    <button
      className={`w-full px-3 py-1.5 text-left pl-9 ${
        effectiveDatasource === datasourceId && effectiveProject === target
          ? 'bg-blue-50 text-blue-700 font-medium'
          : 'text-gray-600 hover:bg-gray-50'
      }`}
      onClick={() => setFilter(datasourceId, target)}
    >
      {target}
    </button>
  )
}

function inferDatasource(projectName: string, datasources: DatasourceGroup[]): string {
  for (const ds of datasources) {
    if (ds.projects.includes(projectName)) return ds.id
    if ((ds.bug_targets ?? []).includes(projectName)) return ds.id
    if ((ds.repositories ?? []).includes(projectName)) return ds.id
  }
  return ''
}
