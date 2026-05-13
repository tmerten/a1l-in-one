import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useSprints } from '../hooks/useMetrics'

const RELATIVE_PRESETS = [
  { label: 'Last 7 days', days: 7 },
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 90 days', days: 90 },
  { label: 'This month', days: 0, thisMonth: true },
  { label: 'This quarter', days: 0, thisQuarter: true },
]

function presetValue(p: typeof RELATIVE_PRESETS[number]): string {
  if ('thisMonth' in p) return 'preset-month'
  if ('thisQuarter' in p) return 'preset-quarter'
  return `preset-${p.days}`
}

function applyPreset(p: typeof RELATIVE_PRESETS[number]): { from: string; to: string } {
  const now = new Date()
  const to = now.toISOString().split('T')[0]
  if ('thisMonth' in p) {
    const from = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0]
    return { from, to }
  }
  if ('thisQuarter' in p) {
    const q = Math.floor(now.getMonth() / 3)
    const from = new Date(now.getFullYear(), q * 3, 1).toISOString().split('T')[0]
    return { from, to }
  }
  const fromDate = new Date(now)
  fromDate.setDate(fromDate.getDate() - p.days)
  return { from: fromDate.toISOString().split('T')[0], to }
}

export default function TimeframeSelector() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { data: sprints } = useSprints()

  const fromParam = searchParams.get('from')
  const toParam = searchParams.get('to')
  const sprintId = searchParams.get('sprint_id')

  // Compute current select value
  const currentValue = sprintId
    ? sprintId
    : (() => {
        const matched = RELATIVE_PRESETS.find(p => {
          const { from } = applyPreset(p)
          return fromParam === from
        })
        return matched ? presetValue(matched) : (fromParam ? 'custom' : 'preset-30')
      })()

  const setPreset = useCallback((p: typeof RELATIVE_PRESETS[number]) => {
    const { from, to } = applyPreset(p)
    const params = new URLSearchParams(searchParams)
    params.set('from', from)
    params.set('to', to)
    params.delete('sprint_id')
    setSearchParams(params, { replace: true })
  }, [searchParams, setSearchParams])

  const setRange = useCallback((newFrom: string, newTo: string) => {
    const params = new URLSearchParams(searchParams)
    if (newFrom) params.set('from', newFrom); else params.delete('from')
    if (newTo) params.set('to', newTo); else params.delete('to')
    params.delete('sprint_id')
    setSearchParams(params, { replace: true })
  }, [searchParams, setSearchParams])

  return (
    <div className="flex items-center gap-2">
      <select
        className="text-sm border border-gray-300 rounded-md px-2 py-1 bg-white"
        value={currentValue}
        onChange={e => {
          const val = e.target.value
          if (val.startsWith('preset-')) {
            const preset = RELATIVE_PRESETS.find(p => presetValue(p) === val)
            if (preset) setPreset(preset)
          } else if (val === 'custom') {
            // keep current range
          } else {
            // sprint ID
            const params = new URLSearchParams(searchParams)
            params.set('sprint_id', val)
            params.delete('from')
            params.delete('to')
            setSearchParams(params, { replace: true })
          }
        }}
      >
        <optgroup label="Presets">
          {RELATIVE_PRESETS.map(p => (
            <option key={presetValue(p)} value={presetValue(p)}>{p.label}</option>
          ))}
          {fromParam && <option value="custom">Custom range</option>}
        </optgroup>
        {sprints && sprints.length > 0 && (
          <optgroup label="Sprints">
            {(sprints as Array<{id: string; name: string; is_active: boolean}>).map(s => (
              <option key={s.id} value={s.id}>
                {s.name}{s.is_active ? ' (active)' : ''}
              </option>
            ))}
          </optgroup>
        )}
      </select>
      {!sprintId && (
        <div className="flex items-center gap-1">
          <input
            type="date"
            className="text-sm border border-gray-300 rounded-md px-2 py-1"
            value={fromParam || ''}
            onChange={e => setRange(e.target.value, toParam || '')}
          />
          <span className="text-gray-400">→</span>
          <input
            type="date"
            className="text-sm border border-gray-300 rounded-md px-2 py-1"
            value={toParam || ''}
            onChange={e => setRange(fromParam || '', e.target.value)}
          />
        </div>
      )}
    </div>
  )
}
