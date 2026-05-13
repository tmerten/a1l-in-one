interface MetricCardProps {
  title: string
  value: string | number
  subtitle?: string
  loading?: boolean
  error?: string | null
}

export default function MetricCard({ title, value, subtitle, loading, error }: MetricCardProps) {
  if (loading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
        <div className="h-8 bg-gray-200 rounded w-1/3"></div>
      </div>
    )
  }
  if (error) {
    return (
      <div className="bg-white rounded-lg border border-red-200 p-4">
        <div className="text-sm text-red-600">{error}</div>
      </div>
    )
  }
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="text-sm text-gray-500">{title}</div>
      <div className="text-2xl font-semibold text-gray-900 mt-1">{value}</div>
      {subtitle && <div className="text-xs text-gray-400 mt-1">{subtitle}</div>}
    </div>
  )
}
