const API_BASE = '/api'

async function fetchJson(path: string, options?: RequestInit) {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    throw new Error(`API error ${resp.status}: ${resp.statusText}`)
  }
  return resp.json()
}

export async function getSyncStatus() {
  return fetchJson('/sync/status')
}

export async function postSyncRun(source?: string, eventType?: string) {
  const params = new URLSearchParams()
  if (source) params.set('source', source)
  if (eventType) params.set('event_type', eventType)
  const resp = await fetch(`${API_BASE}/sync/run?${params}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  if (resp.status === 409) return null
  if (!resp.ok) throw new Error(`API error ${resp.status}: ${resp.statusText}`)
  return resp.json()
}

export async function getSprints(project?: string) {
  const params = new URLSearchParams()
  if (project) params.set('project', project)
  return fetchJson(`/sprints?${params}`)
}

function buildParams(query: Record<string, string | string[] | undefined>): URLSearchParams {
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (!v) continue
    if (Array.isArray(v)) v.forEach(item => params.append(k, item))
    else params.set(k, v)
  }
  return params
}

export async function getMetrics(endpoint: string, query: Record<string, string | string[] | undefined>) {
  return fetchJson(`/metrics/${endpoint}?${buildParams(query)}`)
}

export async function getMetricsTs(endpoint: string, query: Record<string, string | string[] | undefined>) {
  return fetchJson(`/metrics/${endpoint}/ts?${buildParams(query)}`)
}

export async function getProjects(format?: string) {
  const params = new URLSearchParams()
  if (format) params.set('format', format)
  const suffix = params.toString() ? `?${params}` : ''
  return fetchJson(`/projects${suffix}`)
}

export async function getPersons(query: Record<string, string | string[] | undefined>) {
  return fetchJson(`/persons?${buildParams(query)}`)
}

export async function getPersonContributions(personId: string, query: Record<string, string | string[] | undefined>) {
  return fetchJson(`/persons/${personId}/contributions?${buildParams(query)}`)
}

export interface WorkItemsParams {
  status?: 'active' | 'completed'
  datasource?: string
  event_type?: string
  from?: string
  to?: string
  page?: number
  per_page?: number
}

export async function getWorkItems(personId: string, query: WorkItemsParams) {
  return fetchJson(`/persons/${personId}/work-items?${buildParams(query as Record<string, string | string[] | undefined>)}`)
}

export interface CommitsParams {
  from?: string
  to?: string
  page?: number
  per_page?: number
}

export async function getCommits(personId: string, query: CommitsParams) {
  return fetchJson(`/persons/${personId}/commits?${buildParams(query as Record<string, string | string[] | undefined>)}`)
}