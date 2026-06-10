import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts'
import { formatBucket } from '../lib/formatBucket'
import type { SeriesDef } from './StackedBarChart'

type Props = {
  data: Array<Record<string, string | number | null>>
  series: SeriesDef[]
  onToggle: (key: string) => void
  bucketSize: string
  unit?: string
}

export default function MultiLineChart({ data, series, onToggle, bucketSize, unit }: Props) {
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-[220px] text-sm text-gray-400">
        No data for this timeframe
      </div>
    )
  }

  return (
    <div>
      <div className="flex gap-3 mb-2 flex-wrap">
        {series.map(s => (
          <button
            key={s.key}
            onClick={() => onToggle(s.key)}
            className={`flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full border transition-opacity ${
              s.visible ? 'opacity-100' : 'opacity-40'
            }`}
            style={{ borderColor: s.color, color: s.color }}
          >
            <span className="w-2 h-2 rounded-full inline-block" style={{ background: s.color }} />
            {s.label}
          </button>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
          <XAxis
            dataKey="bucket"
            tickFormatter={tick => formatBucket(String(tick), bucketSize)}
            tick={{ fontSize: 11, fill: '#9ca3af' }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis tick={{ fontSize: 11, fill: '#9ca3af' }} tickLine={false} axisLine={false} />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 6, border: '1px solid #e5e7eb' }}
            labelFormatter={label => formatBucket(String(label), bucketSize)}
            formatter={(value) => [unit && value != null ? `${value} ${unit}` : value]}
          />
          {series.filter(s => s.visible).map(s => (
            <Line
              key={s.key}
              dataKey={s.key}
              stroke={s.color}
              strokeWidth={2}
              connectNulls
              dot={data.length > 30 ? false : { r: 3, fill: s.color }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
