import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useProjects } from '../hooks/useMetrics'

export default function ProjectFilter() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { data, isLoading } = useProjects()

  const selected = searchParams.get('projects') ?? ''

  const setProject = useCallback((project: string) => {
    const params = new URLSearchParams(searchParams)
    if (project) {
      params.set('projects', project)
    } else {
      params.delete('projects')
    }
    setSearchParams(params, { replace: true })
  }, [searchParams, setSearchParams])

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-500">Project:</span>
      <select
        className="text-sm border border-gray-300 rounded-md px-2 py-1 bg-white min-w-[10rem]"
        value={selected}
        disabled={isLoading}
        onChange={e => setProject(e.target.value)}
      >
        <option value="">All projects</option>
        {(data?.projects || []).map((p: string) => (
          <option key={p} value={p}>{p}</option>
        ))}
      </select>
    </div>
  )
}
