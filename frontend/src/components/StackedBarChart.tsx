import { BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts'
import { formatBucket } from '../lib/formatBucket'

export type SeriesDef = {
  key: string
  label: string
  color: string
  visible: boolean
}

type Props = {
  data: Array<Record<string, string | number>>
  series: SeriesDef[]
  onToggle: (key: string) => void
  bucketSize: string
}

export default function StackedBarChart({ data, series, onToggle, bucketSize }: Props) {
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
            <span className="w-2 h-2 rounded-sm inline-block" style={{ background: s.color }} />
            {s.label}
          </button>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
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
          />
          {series.filter(s => s.visible).map(s => (
            <Bar key={s.key} dataKey={s.key} stackId="a" fill={s.color} radius={[2, 2, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
