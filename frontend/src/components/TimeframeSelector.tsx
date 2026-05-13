"use client"

import { useCallback, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

const RELATIVE_PRESETS = [
  { label: 'Last 7 days', days: 7 },
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 90 days', days: 90 },
]

export default function TimeframeSelector() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [mode, setMode] = useState<'preset' | 'range' | 'sprint'>('preset')

  const fromParam = searchParams.get('from')
  const toParam = searchParams.get('to')
  const sprintId = searchParams.get('sprint_id')

  const setPreset = useCallback((days: number) => {
    const now = new Date()
    const from = new Date(now)
    from.setDate(from.getDate() - days)
    const params = new URLSearchParams(searchParams)
    params.set('from', from.toISOString().split('T')[0])
    params.set('to', now.toISOString().split('T')[0])
    params.delete('sprint_id')
    setSearchParams(params, { replace: true })
    setMode('preset')
  }, [searchParams, setSearchParams])

  const setRange = useCallback((newFrom: string, newTo: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('from', newFrom)
    params.set('to', newTo)
    params.delete('sprint_id')
    setSearchParams(params, { replace: true })
    setMode('range')
  }, [searchParams, setSearchParams])

  return (
    <div className="flex items-center gap-2">
      <select
        className="text-sm border border-gray-300 rounded-md px-2 py-1 bg-white"
        value={sprintId || 'preset'}
        onChange={e => {
          const val = e.target.value
          if (val === 'preset') {
            setPreset(30)
          } else {
            const params = new URLSearchParams(searchParams)
            params.set('sprint_id', val)
            params.delete('from')
            params.delete('to')
            setSearchParams(params, { replace: true })
            setMode('sprint')
          }
        }}
      >
        <option value="preset">— Select timeframe —</option>
        <optgroup label="Presets">
          {RELATIVE_PRESETS.map(p => (
            <option key={p.days} value={`preset-${p.days}`}>{p.label}</option>
          ))}
        </optgroup>
      </select>
      {mode !== 'sprint' && (
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
